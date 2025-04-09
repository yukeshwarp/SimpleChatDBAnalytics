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
if 'Analysis' not in st.session_state:
    st.session_state['Analysis'] = ""



tab1, tab2 = st.tabs(["Chat", "Analytics"])

# Streamlit App
with tab1:
    st.title("Chat DB Analytics")

    with st.sidebar:
        # Option to choose filtering method (by date range or number of entries)
        filter_option = st.radio("Filter by:", ("Date Range", "Number of Entries", "Custom Date Range"))

        if filter_option == "Date Range":
            range_opt = st.selectbox("Range by:", ("Monthly", "Quarterly"))

            if range_opt == "Monthly":
                col1, col2 = st.columns([1, 1])
                with col1:
                    Mont = "01"
                    Mont = st.radio("Month:", ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"))
                with col2:
                    yr = "2023"
                    yr = st.radio("Year:", ("2023", "2024", "2025"))
                if Mont=="02":
                    start_date = yr + '/' + Mont + '/' + "01"
                    end_date = yr + '/' + Mont + '/' + "28"
                elif Mont=="01" or Mont=="03" or Mont=="05" or Mont=="07" or Mont=="08" or Mont=="10" or Mont=="12":
                    start_date = yr + '/' + Mont + '/' + "01"
                    end_date = yr + '/' + Mont + '/' + "31"
                else:
                    start_date = yr + '/' + Mont + '/' + "01"
                    end_date = yr + '/' + Mont + '/' + "30"
                limit = None  # Disable the limit slider for date range filtering
                start_offset = None  # Disable the offset for date range filtering

            elif range_opt == "Quarterly":
                col1, col2 = st.columns([1, 1])
                with col1:
                    quarter = st.radio("Quarter:", ("Q1", "Q2", "Q3", "Q4"))
                with col2:
                    yr = st.radio("Year:", ("2023", "2024", "2025"))

                # Determine the start and end date based on the selected quarter
                if quarter == "Q1":
                    start_date = yr + "/01/01"
                    end_date = yr + "/03/31"
                elif quarter == "Q2":
                    start_date = yr + "/04/01"
                    end_date = yr + "/06/30"
                elif quarter == "Q3":
                    start_date = yr + "/07/01"
                    end_date = yr + "/09/30"
                elif quarter == "Q4":
                    start_date = yr + "/10/01"
                    end_date = yr + "/12/31"
                limit = None  # Disable the limit slider for date range filtering
                start_offset = None  # Disable the offset for date range filtering

        elif filter_option == "Custom Date Range":
            # Custom date range input
            start_date = st.date_input("Start Date")
            end_date = st.date_input("End Date")

            # Format the selected dates as strings
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")

            limit = None  # Disable the limit slider for custom date range filtering
            start_offset = None  # Disable the offset for custom date range filtering

        elif filter_option == "Number of Entries":
            # Slider to select the range of entries to fetch
            query_len = """SELECT VALUE COUNT(c.id) FROM c """
            res = list(container.query_items(query=query_len, enable_cross_partition_query=True))
            num_ent = res[0]
            limit = st.slider("Select the number of entries to fetch", min_value=1000, max_value=num_ent, value=2000, step=100)
            start_offset = st.slider("Select the start offset", min_value=0, max_value=limit, value=0, step=100)
            start_date = None  # Disable the date range inputs for number of entries filtering
            end_date = None  # Disable the date range inputs for number of entries filtering
        st.write("---")
        # Fetch button
        fetch_button = st.button("Fetch Data")

        if fetch_button:
            try:
                if filter_option == "Date Range":
                    # Handle both Monthly and Quarterly
                    start_date_obj = datetime.strptime(start_date, "%Y/%m/%d")
                    end_date_obj = datetime.strptime(end_date, "%Y/%m/%d")

                    start_date_str = start_date_obj.strftime("%Y-%m-%dT%H:%M:%S.000000Z")
                    end_date_str = end_date_obj.strftime("%Y-%m-%dT%H:%M:%S.000000Z")

                    query = f"SELECT c.id, c.TimeStamp, c.AssistantName, c.ChatTitle FROM c WHERE c.TimeStamp BETWEEN '{start_date_str}' AND '{end_date_str}' ORDER BY c.TimeStamp DESC"
                elif filter_option == "Custom Date Range":
                    # Use the custom date range selected by the user
                    query = f"SELECT c.id, c.TimeStamp, c.AssistantName, c.ChatTitle FROM c WHERE c.TimeStamp BETWEEN '{start_date_str}T00:00:00.000000Z' AND '{end_date_str}T23:59:59.999999Z' ORDER BY c.TimeStamp DESC"
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

# Analytics Tab
with tab2:
    st.title("Analytics")
    if st.session_state["Analysis"] == "":
        query_ana = """SELECT c.TimeStamp, c.ChatTitle FROM c"""
        items_ana = list(container.query_items(query=query_ana, enable_cross_partition_query=True))
        content = ""
        for i in range(4000):
            content += items_ana[i]["TimeStamp"] + items_ana[i]["ChatTitle"][:30]
        content = preprocess_text(content)
        response = llmclient.chat.completions.create(
                        model="gpt-4o",
                        messages=[ 
                            {"role": "system", "content": "You are an expert product analyst who analyses software products based on the user statistics from user database."},
                            {"role": "user", "content": f"""
                                Do a Yearly and Quarterly analysis on the given content and present it in a human readable format.
                                content: 
                                {content}
                                """
                            }
                        ],
                        temperature=0.7,
                    )

        st.session_state["Analysis"] = response.choices[0].message.content
    st.write(st.session_state["Analysis"])
