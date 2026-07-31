"""
Streamlit frontend with SSE live progress updates.
"""
import streamlit as st
import requests
import json
import uuid

BASE_URL = "http://localhost:8000"

st.set_page_config(
    page_title="PACK & GO – One Platform for Every Journey",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("PACK & GO")
st.header("One Platform for Every Journey")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar for live progress
with st.sidebar:
    st.header("Agent Progress")
    progress_container = st.empty()

st.header("Plan your next adventure with multi-agent intelligence.")

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

user_input = st.chat_input("Where do you want to travel? (e.g., Plan a 5-day luxury trip to Paris)")

if user_input:
    # Always generate a fresh thread_id so new queries never inherit stale
    # LangGraph checkpointer state from a previous conversation.
    fresh_thread_id = str(uuid.uuid4())

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
        
    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        plan_placeholder = st.empty()
        
        payload = {
            "question": user_input,
            "thread_id": fresh_thread_id,
            "remember_me": True
        }
        
        agent_history = []
        
        try:
            # Stream the SSE response
            response = requests.post(f"{BASE_URL}/plan/stream", json=payload, stream=True)
            
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode("utf-8")
                        if decoded_line.startswith("data: "):
                            data_str = decoded_line[len("data: "):]
                            try:
                                event = json.loads(data_str)
                                status = event.get("status")
                                agent = event.get("agent")
                                msg = event.get("message")
                                
                                if status == "running":
                                    status_placeholder.info(f"🔄 **{agent}**: {msg}")
                                    if agent and agent not in agent_history and agent != "System":
                                        agent_history.append(agent)
                                    
                                    # Update sidebar
                                    sidebar_html = "<ul>"
                                    for a in agent_history:
                                        sidebar_html += f"<li>✅ {a}</li>"
                                    sidebar_html += "</ul>"
                                    progress_container.markdown(sidebar_html, unsafe_allow_html=True)
                                    
                                elif status == "done":
                                    status_placeholder.success("✅ Travel plan complete!")
                                    plan_data = event.get("data") or {}
                                    
                                    # Format the output nicely
                                    itinerary = plan_data.get("itinerary") or []
                                    budget = plan_data.get("budget") or {}
                                    critic = plan_data.get("critic_review") or {}
                                    
                                    # Use a list to build markdown
                                    md_lines = []
                                    md_lines.append("### 🗺️ Final Itinerary")
                                    
                                    currency = budget.get('currency', '')
                                    total_est = budget.get('total_estimated', 'N/A')
                                    md_lines.append(f"**💰 Estimated Total Cost**: {total_est} {currency}")
                                    md_lines.append("")
                                    
                                    for day in itinerary:
                                        day_num = day.get('day_number', '?')
                                        theme = day.get('theme', 'No Theme')
                                        md_lines.append(f"<details><summary><b>Day {day_num}: {theme}</b></summary>")
                                        
                                        hotel = day.get('hotel') or {}
                                        h_name = hotel.get('name', 'N/A')
                                        h_price = hotel.get('price_per_night', 'N/A')
                                        md_lines.append(f"<ul>")
                                        md_lines.append(f"<li><b>🏨 Hotel:</b> {h_name} ({h_price}/night)</li>")
                                        
                                        md_lines.append(f"<li><b>📍 Attractions:</b>")
                                        md_lines.append("<ul>")
                                        for attr in day.get('attractions') or []:
                                            place = attr.get('place') or {}
                                            md_lines.append(f"<li>{attr.get('timing', 'Anytime')}: {place.get('name', 'N/A')} ({place.get('entry_fee', 'Free')})</li>")
                                        md_lines.append("</ul></li>")
                                        
                                        md_lines.append(f"<li><b>🍽️ Meals:</b>")
                                        md_lines.append("<ul>")
                                        for meal in day.get('meals') or []:
                                            md_lines.append(f"<li>{meal.get('meal_type', 'Meal')}: {meal.get('restaurant_name', 'N/A')} - {meal.get('estimated_cost', 'N/A')}</li>")
                                        md_lines.append("</ul></li>")
                                        
                                        transport = day.get('transport') or {}
                                        md_lines.append(f"<li><b>🚗 Transport:</b> {transport.get('mode', 'N/A')} ({transport.get('estimated_cost', 'N/A')})</li>")
                                        md_lines.append(f"<li><b>💸 Est. Day Cost:</b> {day.get('estimated_day_cost', 'N/A')}</li>")
                                        md_lines.append("</ul>")
                                        md_lines.append("</details>")
                                        md_lines.append("")
                                    
                                    if critic:
                                        md_lines.append("---")
                                        md_lines.append("### 📊 Critic Review")
                                        md_lines.append(f"**Overall Score:** {critic.get('overall_score', 'N/A')}/10")
                                        md_lines.append("")
                                        highlights = critic.get('highlights') or []
                                        if highlights:
                                            md_lines.append("**Highlights:**")
                                            for h in highlights:
                                                md_lines.append(f"- ✅ {h}")
                                        
                                        warnings = critic.get('warnings') or []
                                        if warnings:
                                            md_lines.append("")
                                            md_lines.append("**Warnings:**")
                                            for w in warnings:
                                                md_lines.append(f"- ⚠️ {w}")
                                                
                                    md_output = "\n".join(md_lines)
                                    plan_placeholder.markdown(md_output, unsafe_allow_html=True)
                                    st.session_state.messages.append({"role": "assistant", "content": md_output})
                                    
                                elif status == "error":
                                    status_placeholder.error(f"❌ Error: {msg}")
                                    break
                            except json.JSONDecodeError:
                                pass
            else:
                st.error(f"Failed to connect to API. Status code: {response.status_code}")
        except Exception as e:
            st.error(f"Connection error: {e}")
