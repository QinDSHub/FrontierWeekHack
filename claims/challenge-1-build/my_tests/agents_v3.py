"""
Challenge 1: Build Agents — Insurance Claims Processing
Claims Triage Agent and Claims Decision Agent for ClaimSight Insurance.

Usage:
    python agents.py

Builds both agents with system prompts, tools, and conversation handling.
"""

# adjustment-3: add one more agent for test if-else workflow in Foundry

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FunctionTool, PromptAgentDefinition
from azure.identity import DefaultAzureCredential
from openai.types.responses.response_input_param import FunctionCallOutput


# Resolve repo root by finding .env in parent directories.
def _find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".env").exists():
            return parent
    return Path(__file__).resolve().parents[2]


REPO_ROOT = _find_repo_root()

# Load environment
env_path = REPO_ROOT / ".env"
load_dotenv(env_path)

PROJECT_CONNECTION_STRING = os.getenv("PROJECT_CONNECTION_STRING")
MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-5.4")
CLAIMS_DATA_PATH = Path(__file__).resolve().parent / "claims_data.json"

SAVE_OUTPUT_PATH = Path(__file__).resolve().parent / "claims_process_suggestion.json"


def _load_claim_batch() -> list[dict]:
    """Load claim records to send as a batch payload in demo requests."""
    with open(CLAIMS_DATA_PATH, "r") as f:
        data = json.load(f)
    return data.get("claims", [])

# =============================================================================
# Tool Function: assess_claim
# This is already implemented — agents can call this to get claim risk analysis
# =============================================================================

def assess_claim(claim_id: str) -> str:
    """
    Reads claims_data.json and checks if a claim's metrics are within acceptable thresholds.
    Returns a JSON string with the analysis.
    """
    with open(CLAIMS_DATA_PATH, "r") as f:
        data = json.load(f)

    claim = None
    for c in data["claims"]:
        if c["claim_id"] == claim_id:
            claim = c
            break

    if not claim:
        return json.dumps({"error": f"Claim '{claim_id}' not found"})

    results = {
        "claim_id": claim["claim_id"],
        "type": claim["type"],
        "claimant": claim["claimant"],
        "date_filed": claim["date_filed"],
        # "status": claim["status"],
        "documents_submitted": claim["documents_submitted"],
        "flags": [],
        "all_metrics": {},
    }

    for metric, reading in claim["metrics"].items():
        value = reading["value"]
        threshold = claim["thresholds"][metric]
        in_spec = threshold["min"] <= value <= threshold["max"]

        results["all_metrics"][metric] = {
            "value": value,
            "unit": reading["unit"],
            "min": threshold["min"],
            "max": threshold["max"],
            "in_spec": in_spec,
        }

        if not in_spec:
            deviation = ""
            if value > threshold["max"]:
                pct = ((value - threshold["max"]) / threshold["max"]) * 100
                deviation = f"{pct:.1f}% above max"
            elif value < threshold["min"]:
                pct = ((threshold["min"] - value) / threshold["min"]) * 100
                deviation = f"{pct:.1f}% below min"

            results["flags"].append({
                "metric": metric,
                "value": value,
                "unit": reading["unit"],
                "threshold_min": threshold["min"],
                "threshold_max": threshold["max"],
                "deviation": deviation,
            })

    return json.dumps(results, indent=2)


# Tool definition for the agent (Foundry FunctionTool format)
ASSESS_CLAIM_TOOL = FunctionTool(
    name="assess_claim",
    description="Assess an insurance claim's metrics against acceptable thresholds. Returns flags if any metrics are outside acceptable ranges (completeness too low, fraud risk too high, etc.).",
    parameters={
        "type": "object",
        "properties": {
            "claim_id": {
                "type": "string",
                "description": "The claim ID (e.g., 'CLM-001') to assess",
            }
        },
        "required": ["claim_id"],
        "additionalProperties": False,
    },
    strict=False,
)


# =============================================================================
# Claims Triage Agent
# =============================================================================

class ClaimsAgentNew:
    def __init__(self):
        self.agent = None
        self.client = None
        self.openai = None

    def create(self):
        """Create the claims triage agent in Foundry."""
        self.client = AIProjectClient(
            endpoint=PROJECT_CONNECTION_STRING,
            credential=DefaultAzureCredential(),
        )
        self.openai = self.client.get_openai_client()

        system_prompt = """
        You are an **Insurance Claims Triage Specialist** for **ClaimSight Insurance**.
        When asked to assess insurance claims, use the `assess_claim` tool **once for each claim**.
        For each claim, perform the following tasks:

        ### 1. Determine the Claim Classification
        Classify the claim according to these rules:
        * **normal (✅)**: All metrics have `in_spec = true`.
        * **critical (🔴)**: The **Fraud Risk Score** metric has `in_spec = false`, **and** its value exceeds the maximum threshold by a significant margin (i.e., the deviation above the maximum threshold is substantially large).
        * **warning (⚠️)**: Any claim that does not meet the criteria for **normal** or **critical**.

        ---

        ### 2. Include Basic Claim Information
        For each claim, include:
        * Claim ID
        * Claim Type
        * Claimant Name

        ---

        ### 3. Summarize Violated Metrics
        For every metric where `in_spec = false`, report:
        * Metric name
        * Current value
        * Violated threshold (minimum or maximum)
        * Deviation from the threshold
        * Brief explanation of the issue
        If no metrics are out of specification, explicitly state that all metrics passed validation.

        ---

        ### 4. Recommend the Appropriate Action
        Determine the recommended action using the following priority order:
        1. **approve** – The claim is classified as **normal**.
        2. **investigate** – The claim is classified as **critical**.
        3. **request_documents** – The claim fails the **Completeness** metric.
        4. **partial_deny** – The claim fails any other metric(s) not covered by the rules above.

        ---

        ### 5. Recommend Next Steps
        Provide concise, specific, and actionable recommendations for the claims adjuster based on the identified issues.

        ---

        ### 6. Estimate Urgency
        Assign an urgency level based on the claim classification:
        * **low** → normal
        * **medium** → warning
        * **high** → critical

        ---

        ### Output Requirements
        Produce a concise, well-structured summary for each claim. Include:
        * Claim Information
        * Classification
        * Failed Metrics (if any)
        * Recommended Action
        * Urgency
        * Next Steps

        Be concise and structured.
        """

        self.agent = self.client.agents.create_version(
            agent_name="claims-agent",
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT_NAME,
                instructions=system_prompt,
                tools=[ASSESS_CLAIM_TOOL],
            ),
        )

        return self.agent

    def run(self, input_text: str) -> str:
        """Run the claims triage agent with the given input."""
        conversation = self.openai.conversations.create()

        response = self.openai.responses.create(
            input=input_text,
            conversation=conversation.id,
            extra_body={"agent_reference": {"name": self.agent.name, "type": "agent_reference"}},
        )

        # Handle function call loops
        while True:
            function_calls = [item for item in response.output if item.type == "function_call"]
            if not function_calls:
                break

            input_list = []
            for item in function_calls:
                if item.name == "assess_claim":
                    args = json.loads(item.arguments)
                    result = assess_claim(args["claim_id"])
                else:
                    result = json.dumps({"error": f"Unknown tool '{item.name}'"})

                input_list.append(
                    FunctionCallOutput(
                        type="function_call_output",
                        call_id=item.call_id,
                        output=result,
                    )
                )

            response = self.openai.responses.create(
                input=input_list,
                conversation=conversation.id,
                extra_body={"agent_reference": {"name": self.agent.name, "type": "agent_reference"}},
            )

        self.openai.conversations.delete(conversation_id=conversation.id)

        output = response.output_text
        with open(SAVE_OUTPUT_PATH, 'w') as f:
            json.dump(output, f, indent=4)

        return output

    def cleanup(self):
        """Delete the agent version and close connections."""
        if self.agent:
            self.client.agents.delete_version(
                agent_name=self.agent.name,
                agent_version=self.agent.version,
            )
        if self.client:
            self.client.close()


# =============================================================================
# Double Check Agent for those approval claims
# =============================================================================

class DoubleCheckAgentNew:
    def __init__(self):
        self.agent = None
        self.client = None
        self.openai = None

    def create(self):
        """Create the double check agent in Foundry"""
        self.client = AIProjectClient(
            endpoint=PROJECT_CONNECTION_STRING,
            credential=DefaultAzureCredential(),
        )
        self.openai = self.client.get_openai_client()

        system_prompt = """
        You are a senior claims double check reviewer for outputs from claims agent.
        Determine whether the agent's output indicates that the claim should be approved: Ture, False  
        Be concise and structured.
        """
        
        self.agent = self.client.agents.create_version(
            agent_name="double-check-agent",
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT_NAME,
                instructions=system_prompt,
            ),
        )

        return self.agent

    def run(self, input_text: str) -> str:
        """Run the double check agent with the given input."""
        conversation = self.openai.conversations.create()

        response = self.openai.responses.create(
            input=input_text,
            conversation=conversation.id,
            extra_body={"agent_reference": {"name": self.agent.name, "type": "agent_reference"}},
        )

        self.openai.conversations.delete(conversation_id=conversation.id)
        
        return response.output_text


    def cleanup(self):
        """Delete the agent version and close connections."""
        if self.agent:
            self.client.agents.delete_version(
                agent_name=self.agent.name,
                agent_version=self.agent.version,
            )
        if self.client:
            self.client.close()


# =============================================================================
# Main — Test both agents
# =============================================================================

def main():
    if not PROJECT_CONNECTION_STRING:
        print("❌ PROJECT_CONNECTION_STRING not set. Run challenge 0 first!")
        sys.exit(1)

    print("=== Claims Triage Agent New===")
    print("Creating agent...")

    triage_agent = ClaimsAgentNew()
    triage_agent.create()
    print(f"✅ Created: {triage_agent.agent.name} (version {triage_agent.agent.version})")

    print("\nLoading and Assessing all claims...")
    claim_batch = _load_claim_batch()
    claim_ids = [claim["claim_id"] for claim in claim_batch]
    triage_result = triage_agent.run(
        "You are receiving a batch payload of claims that must be assessed in one run. "
        "Use assess_claim for each claim_id in the payload and summarize all flags.\n\n"
        f"BATCH_CLAIM_IDS: {json.dumps(claim_ids)}\n"
        "BATCH_CLAIM_DATA:\n"
        f"{json.dumps(claim_batch, indent=2)}"
    )
    print(triage_result)

    print("\n=== Double Check Agent New ===")
    print("Creating agent...")

    check_agent = DoubleCheckAgentNew()
    check_agent.create()
    print(f"✅ Created: {check_agent.agent.name} (version {check_agent.agent.version})")

    print("\nDouble check those approval claim batch for next auto message to customers...")
    print("Info: Here is just test from raw data, in portal workflow, the input is the output from last agent!")
    # approve_batch = [claim for claim in claim_batch if claim["status"] in {"normal"}]
    check_result = check_agent.run(
        "You are receiving a batch payload of claims. For each claim, double check whether it is approved: true, false.\n\n"
        "HIGH_RISK_CLAIM_BATCH:\n"
        f"{json.dumps(triage_result, indent=2)}"
    )
    print(check_result)

    # Cleanup — comment out to keep agents visible in the Foundry portal
    # print("\nCleaning up agents...")
    # triage_agent.cleanup()
    # decision_agent.cleanup()
    # print("✅ Done!")


if __name__ == "__main__":
    main()
