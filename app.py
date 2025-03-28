import streamlit as st
from azure.cosmos import CosmosClient
from topicmodelling_dev import extract_topics_from_text
import os
from openai import AzureOpenAI

ENDPOINT = os.getenv("DB_ENDPOINT")
KEY =os.getenv("DB_KEY")
DATABASE_NAME = os.getenv("DB_NAME")
CONTAINER_NAME = os.getenv("DB_CONTAINER_NAME")
# Redis connection details (replace with your actual values

# LLM setup
llmclient = AzureOpenAI(
    azure_endpoint=os.getenv("LLM_ENDPOINT"),
    api_key=os.getenv("LLM_KEY"),
    api_version="2024-10-01-preview",
)

# Initialize session state
if 'chats' not in st.session_state:
    st.session_state['chats'] = []
if 'messages' not in st.session_state:
    st.session_state['messages'] = []

# Initialize CosmosClient
client = CosmosClient(ENDPOINT, KEY)
database = client.get_database_client(DATABASE_NAME)
container = database.get_container_client(CONTAINER_NAME)
From = ""
To = ""
# Streamlit App
st.title("ChatDB Analytics")

with st.sidebar:
    # Slider to select the range of entries to fetch
    
    limit = st.slider("Select the number of entries to fetch", min_value=2000, max_value=20000, value=4000, step=100)
    start_offset = st.slider("Select the start offset", min_value=0, max_value=limit, value=0, step=100)

    # Fetch button
    fetch_button = st.button("Fetch Data")
    
    if fetch_button:
        # Create Cosmos query to fetch data
        query = f"SELECT c.id, c.TimeStamp, c.AssistantName, c.ChatTitle FROM c ORDER BY c.TimeStamp DESC OFFSET {start_offset} LIMIT {limit}"

        try:
            items = list(container.query_items(query=query, enable_cross_partition_query=True))

            # Display results
            if items:
                st.write(f"Displaying {len(items)} chat entries starting from offset {start_offset}:")

                # Limit chat title to 50 characters for readability
                
                for i in range(len(items)):
                    items[i]["ChatTitle"] = items[i]["ChatTitle"][:50]
                st.session_state['chats'] = list(items)
            else:
                st.write("No data found for the selected range.")
            From = items[0]['TimeStamp'][:10]
            To = items[-1]['TimeStamp'][:10]
            
        except Exception as e:
            st.write(f"An error occurred: {str(e)}")

# Display previous messages (for chat history)
st.markdown('<div class="main-header">Interactive Chat Insights</div>', unsafe_allow_html=True)
for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
st.markdown('</div>', unsafe_allow_html=True)

chat_titles = [ chat["ChatTitle"] for chat in st.session_state["chats"]]
chat_titles_text = "\n".join(chat_titles)  # Join chat titles into a single text block
topics = extract_topics_from_text(chat_titles_text)
# st.write(chat_titles_text)

if From:          
    trend_analysis_response = llmclient.chat.completions.create(
        model="gpt-4o",
        messages=[ 
            {"role": "system", "content": "You are an expert data analyst analyzing trends from user interaction data."},
            {"role": "user", "content": f"""
                Analyze the following chat titles for trends, topics, and insights based on user interactions. 
                Provide a summary of key trends and observations.
                
                Chat Titles:
                {chat_titles_text}
            """}
        ],
        temperature=0.7,
        stream=False,  # We want a complete response, not a stream
    )

    # Display the trend analysis at the top
    trend_analysis = trend_analysis_response.choices[0].message.content
    st.write("### Trend Analysis")
    st.session_state["messages"].append({"role": "assistant", "content":trend_analysis})
    st.markdown(trend_analysis)
            

with st.sidebar:
    st.write(f"Data Range")
    st.write(f"From: {From}")
    st.write(f"To: {To}")
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
                        {chat_titles_text}
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
