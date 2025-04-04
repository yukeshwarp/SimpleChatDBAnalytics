import streamlit as st
from datetime import datetime
from cloud_config import *
from topicmodelling_dev import extract_topics_from_text
from preprocessor import preprocess_text
from azure.cosmos import CosmosClient


client = CosmosClient(ENDPOINT, KEY)
database = client.get_database_client(DATABASE_NAME)
container = database.get_container_client(CONTAINER_NAME)

# Initialize session state
if 'chats' not in st.session_state:
    st.session_state['chats'] = []
if 'messages' not in st.session_state:
    st.session_state['messages'] = []

# Streamlit App
st.title("Chat DB Analytics")

with st.sidebar:
    # Option to choose filtering method (by date range or number of entries)
    filter_option = st.radio("Filter by:", ("Date Range", "Number of Entries"))

    if filter_option == "Date Range":
        # Date Range Picker for filtering results by date
        start_date = st.date_input("Select start date", datetime.today())
        end_date = st.date_input("Select end date", datetime.today())
        limit = None  # Disable the limit slider for date range filtering
        start_offset = None  # Disable the offset for date range filtering

    elif filter_option == "Number of Entries":
        # Slider to select the range of entries to fetch
        query_len = """SELECT VALUE COUNT(c.id) FROM c """
        res = list(container.query_items(query=query_len, enable_cross_partition_query=True))
        num_ent = res[0]
        limit = st.slider("Select the number of entries to fetch", min_value=1000, max_value=num_ent, value=2000, step=100)
        start_offset = st.slider("Select the start offset", min_value=0, max_value=limit, value=0, step=100)
        start_date = None  # Disable the date range inputs for number of entries filtering
        end_date = None  # Disable the date range inputs for number of entries filtering

    # Fetch button
    fetch_button = st.button("Fetch Data")
    
    if fetch_button:
        try:
            if filter_option == "Date Range":
                start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%S.000000Z")
                end_date_str = end_date.strftime("%Y-%m-%dT%H:%M:%S.000000Z")
                query = f"SELECT c.id, c.TimeStamp, c.AssistantName, c.ChatTitle FROM c WHERE c.TimeStamp BETWEEN '{start_date_str}' AND '{end_date_str}' ORDER BY c.TimeStamp DESC"

            elif filter_option == "Number of Entries":
                query = f"SELECT c.id, c.TimeStamp, c.AssistantName, c.ChatTitle FROM c ORDER BY c.TimeStamp DESC OFFSET {start_offset} LIMIT {limit}"

            # Query Cosmos DB
            items = list(container.query_items(query=query, enable_cross_partition_query=True))

            # Display results
            if items:
                st.write(f"Displaying {len(items)} chat entries:")
                for i in range(len(items)):
                    items[i]["ChatTitle"] = items[i]["ChatTitle"][:50]
                st.session_state['chats'] = list(items)
            else:
                st.write("No data found for the selected range.")
            
        except Exception as e:
            st.write(f"An error occurred: {str(e)}")

# Display previous messages (for chat history)
st.markdown('<div class="main-header">Interactive Chat Insights</div>', unsafe_allow_html=True)
for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
st.markdown('</div>', unsafe_allow_html=True)

chat_titles = [chat["ChatTitle"][:50] for chat in st.session_state["chats"]]
chat_titles_text = "\n".join(chat_titles)  # Join chat titles into a single text block
# st.write(chat_titles_text)
topics = extract_topics_from_text(chat_titles_text)
processed_chat_titles = preprocess_text(chat_titles_text)

if chat_titles:          
    # Send chat titles to LLM for trend analysis
    trend_analysis_response = llmclient.chat.completions.create(
        model="gpt-4o",
        messages=[ 
            {"role": "system", "content": "You are an expert data analyst analyzing trends from user interaction data."},
            {"role": "user", "content": f"""
                Analyze the following chat titles for trends, topics, and insights based on user interactions. 
                Provide a summary of key trends and observations.
                
                Chat Titles:
                {processed_chat_titles}
            """}
        ],
        temperature=0.7,
        stream=False,  # We want a complete response, not a stream
    )

    # Display the trend analysis at the top
    trend_analysis = trend_analysis_response.choices[0].message.content
    st.write("### Trend Analysis")
    st.session_state["messages"].append({"role": "assistant", "content": trend_analysis})
    st.markdown(trend_analysis)

with st.sidebar:
    if filter_option == "Date Range":
        st.write(f"Data Range")
        st.write(f"From: {start_date}")
        st.write(f"To: {end_date}")
    elif filter_option == "Number of Entries":
        st.write(f"Entries Fetching")
        st.write(f"Limit: {limit}")
        st.write(f"Start Offset: {start_offset}")

# User input for questions
if prompt := st.chat_input("Ask a question"):
    # Extract only ChatTitle from the fetched data for LLM

    bot_response = ""
    if chat_titles:
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.spinner("Thinking..."):
            response_stream = llmclient.chat.completions.create(
                model="gpt-4o",
                messages=[ 
                    {"role": "system", "content": "You are an expert product analyst who analyses software products based on the user statistics from user database."},
                    {"role": "user", "content": f"""
                        Answer the user's prompt based on the following data from the database. 
                        The database contains usage history of user questions and AI responses from an AI-assisted chatbot interface, specifically used for legal advice.

                        User Chat Titles: 
                        {processed_chat_titles}
                        Highlighted topics:
                        {topics}

                        ---
                        Prompt: {prompt}

                        ---
                        Intelligently analyze the user's intent in the prompt and provide an insightful answer, utilizing relevant data and context from the chat titles.
                        """
                    }
                ],
                temperature=0.7,
                stream=True,
            )
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            for chunk in response_stream:
                if chunk.choices:
                    bot_response += chunk.choices[0].delta.content or ""
                    message_placeholder.markdown(bot_response)
        st.session_state["messages"].append({"role": "assistant", "content": bot_response})
        
    else:
        st.warning("Please fetch and analyze topics first.")
