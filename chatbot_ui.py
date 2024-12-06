import streamlit as st
import os
import requests
from together import Together
import json

def parse_timestamp_question(question):
    """
    Uses an LLaMA call to determine if a question references a lecture and timestamp.
    Returns a list with lecture number and a tuple of start and end times in seconds.

    Args:
        question (str): The input question.

    Returns:
        list: [lecture_number, (start_time_in_seconds, end_time_in_seconds)] if valid timestamp is found.
        None: If no timestamp reference is detected.
    """
    client = Together()

    instructions = f"""
    Given the following question: "{question}"

    Identify if it references a lecture and a specific timestamp. If so, return the following format:
    [lecture_number, (start_time_in_seconds, end_time_in_seconds)]

    Example:
    Input: "Summarize the first 5 minutes of lecture 4"
    Output: [4, (0, 300)]

    Input: "What is recursion?"
    Output: None

    Return only the specified format, without any extra text or explanation.
    """

    try:
        response = client.chat.completions.create(
            model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
            messages=[
                {"role": "system", "content": "You are a parsing assistant."},
                {"role": "user", "content": instructions}
            ],
            stream=False,
        )

        response_text = response.choices[0].message.content.strip()

        if response_text.lower() == "none":
            return None
        
        try:
            result = eval(response_text)
            if (
                isinstance(result, list)
                and len(result) == 2
                and isinstance(result[0], int)
                and isinstance(result[1], tuple)
                and len(result[1]) == 2
                and all(isinstance(x, (int, float)) for x in result[1])
            ):
                return [result[0], (int(result[1][0]), int(result[1][1]))]
            else:
                return None
        except Exception as e:
            return None
    except Exception as e:
        return None

def process_query(compiled_input, current_question, json_file_path="Bejerano_Sun_224V_Updated.jsonl"):
    """
    Processes the current question to retrieve relevant information from a JSON file.
    If the question contains timestamp-based information, it filters entries based on lecture number and time range.

    Args:
        compiled_input (str): The compiled input query.
        current_question (str): The current user question.
        json_file_path (str): Path to the JSON file containing lecture data.

    Returns:
        list: Filtered lecture entries based on timestamp and lecture number.
    """
    timestamp_info = parse_timestamp_question(current_question)

    if timestamp_info:
        lecture_number, (start_time, end_time) = timestamp_info
        filtered_entries = []

        try:
            with open(json_file_path, "r") as file:
                data = [json.loads(line) for line in file]

            for entry in data:
                if entry.get("document_title") == f"Lecture {lecture_number}":
                    block_metadata = entry.get("block_metadata", {})
                    block_start = block_metadata.get("start_time", 0)
                    block_end = block_metadata.get("end_time", 0)

                    if block_start <= end_time and block_end >= start_time:
                        filtered_entries.append(entry)

            return filtered_entries

        except FileNotFoundError:
            print(f"Error: JSON file '{json_file_path}' not found.")
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            return None

    # default retrieval
    url = "https://search.genie.stanford.edu/stanford_computer_science_106B"
    headers = {"Content-Type": "application/json"}
    payload = {
        "query": [compiled_input], 
        "rerank": True,
        "num_blocks_to_rerank": 10,
        "num_blocks": 3
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"Failed to retrieve data. Status code: {response.status_code}")
        return None

def is_homework_related(question):
    homework_keywords = ["homework", "assignment", "problem set", "pset", "task", "exercise", "solve", "implement"]
    return any(keyword.lower() in question.lower() for keyword in homework_keywords)

def get_response_from_model(history, data, current_question):
    client = Together()
    messages = [
        {
            "role": "system", 
            "content": "Respond as if you are a professor for a computer science class being asked a question, use the information provided to answer the question. Do not include a header in your response, answer the question directly."
        }
    ]
    for entry in history:
        messages.append({"role": "user", "content": entry["question"]})
        messages.append({"role": "assistant", "content": entry["response"]})
    
    messages.append({
        "role": "user",
        "content": f"Using {data}, please explain {current_question}"
    })

    stream = client.chat.completions.create(
        model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        messages=messages,
        stream=True,
    )

    response_text = ""
    for chunk in stream:
        text = chunk.choices[0].delta.content or ""
        response_text += text
    return response_text

def handle_user_input():
    user_input = st.session_state.user_input
    if user_input:
        if is_homework_related(user_input):
            st.error(
                "It seems your question may relate to homework. "
                "Please refer to the official honor code, which does not allow the use of AI to solve or assist in completing the homework."
            )
            proceed = st.radio(
                "Would you like to proceed with this question?",
                options=["Yes", "No"],
                key="proceed_radio",
                index=0
            )

            if proceed == "No":
                st.warning("Please ask a different question.")
                st.session_state.user_input = ""
                return

        compiled_input = " ".join([entry["question"] for entry in st.session_state.history]) + " " + user_input

        data = process_query(compiled_input, user_input)

        if data:
            response = get_response_from_model(st.session_state.history, data, user_input)

            st.session_state.history.append({"question": user_input, "response": response})

        else:
            st.error("Failed to process your question. Please try again.")

        st.session_state.user_input = ""


# Streamlit App
st.set_page_config(layout="wide")

st.title("CS Lecture Chatbot")
st.write("Interact with the chatbot below to ask questions about computer science lectures.")

if "history" not in st.session_state:
    st.session_state.history = []

st.write("### Chat History")
chat_history = st.container()

user_style = """
    padding: 10px;
    border-radius: 10px;
    margin-bottom: 10px;
"""
bot_style = """
    background-color: #848884;
    padding: 10px;
    border-radius: 10px;
    margin-bottom: 10px;
"""

with chat_history:
    for entry in st.session_state.history:
        user_message = f"""
        <div style="{user_style}">
            <b>You:</b> {entry['question']}
        </div>
        """
        bot_message = f"""
        <div style="{bot_style}">
            <b>Bot:</b> {entry['response']}
        </div>
        """
        st.markdown(user_message, unsafe_allow_html=True)
        st.markdown(bot_message, unsafe_allow_html=True)

st.write("---")
st.text_input(
    "Your question:", 
    placeholder="Type your question here...", 
    key="user_input", 
    on_change=handle_user_input
)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    