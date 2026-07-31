"""
Budget Agent for comprehensive travel expense calculation and validation.
Uses the expense calculator and currency conversion tools to ensure exact numerical precision.
"""
from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from utils.llm_loader import invoke_with_fallback
from prompt_library.budget_prompt import SYSTEM_PROMPT
from models.schemas import BudgetBreakdown
from tools.expense_calculator_tool import CalculatorTool
from tools.currency_conversion_tool import CurrencyConverterTool
from logger.logging import get_logger

logger = get_logger(__name__)

def budget_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculates estimated costs for hotels, food, transportation, and activities.
    Integrates external calculation and currency conversion tools dynamically.
    Generates cost-saving adjustment suggestions if the budget is exceeded.
    """
    logger.info("BudgetAgent started.")
    
    preferences = state.get("preferences")
    if not preferences:
        logger.warning("No preferences found in state. Skipping budget calculation.")
        return {"budget_breakdown": None}
    
    # Initialize Tools
    calc_tools = CalculatorTool()
    currency_tool = CurrencyConverterTool()
    
    tools = calc_tools.calculator_tool_list + currency_tool.currency_converter_tool_list
    
    system_message = SystemMessage(content=SYSTEM_PROMPT)
    human_content = (
        f"Destination: {preferences.destination}\n"
        f"Duration: {preferences.duration} days\n"
        f"Total Budget: {preferences.total_budget} {preferences.budget_currency}\n"
        f"Travel Style: {preferences.travel_style}\n"
        f"Group Size: {preferences.group_size}\n"
        f"Is Domestic: {preferences.is_domestic}\n\n"
        "You have access to Calculator and Currency Conversion tools. "
        "Calculate the hotel costs, daily expenses, and total trip expenses. "
        "If Is Domestic is False, you MUST use the currency converter to convert local currency to the user's budget currency. "
        "Return the final JSON strictly adhering to the BudgetBreakdown schema, including adjustment suggestions if over budget."
    )
    
    messages = [system_message, HumanMessage(content=human_content)]
    
    def build_tool_chain(llm):
        return llm.bind_tools(tools)
        
    def build_structured_chain(llm):
        return llm.with_structured_output(BudgetBreakdown)
    
    try:
        # Step 1: Tool calling phase
        response_msg = invoke_with_fallback(build_tool_chain, messages)
        messages.append(response_msg)
        
        # Execute tool calls
        tool_map = {t.name: t for t in tools}
        if hasattr(response_msg, "tool_calls") and response_msg.tool_calls:
            for tool_call in response_msg.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                if tool_name in tool_map:
                    logger.info(f"BudgetAgent executing tool: {tool_name} with args {tool_args}")
                    tool_result = tool_map[tool_name].invoke(tool_args)
                    messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_call["id"]))
        
            # Step 2: Generation phase (Parse to Pydantic)
            final_response = invoke_with_fallback(build_structured_chain, messages)
        else:
            # It didn't call tools, just parse its content into Pydantic
            final_response = invoke_with_fallback(build_structured_chain, messages)
            
        logger.info(f"Budget calculated. Total: {final_response.total_estimated}")
        return {"budget_breakdown": final_response, "completed_agents": ["BudgetAgent"]}
        
    except Exception as e:
        logger.error(f"BudgetAgent failed: {e}")
        # Return fallback
        return {"budget_breakdown": BudgetBreakdown(
            total_estimated=0.0,
            currency=preferences.budget_currency if preferences else "USD",
            categories=[],
            is_within_budget=True,
            adjustment_suggestions=["Error calculating budget. Please verify manually."]
        ), "completed_agents": ["BudgetAgent"]}
