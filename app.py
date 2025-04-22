import streamlit as st
from datetime import datetime
from cloud_config import CONTAINER_NAME, ENDPOINT, DATABASE_NAME, llmclient, KEY
from topicmodelling_dev import extract_topics_from_text
from preprocessor import preprocess_text
from azure.cosmos import CosmosClient

client = CosmosClient(ENDPOINT, KEY)
database = client.get_database_client(DATABASE_NAME)
container = database.get_container_client(CONTAINER_NAME)

# Initialize session state
if "chats" not in st.session_state:
    st.session_state["chats"] = []
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "Analysis" not in st.session_state:
    st.session_state["Analysis"] = ""
if "current_view" not in st.session_state:
    st.session_state["current_view"] = "Chat"  # Default view is Chat

st.title("Chat DB Analytics")

# Navigation buttons
col1, col2 = st.columns([1, 1])
with col1:
    if st.button(
        "Chat View",
        use_container_width=True,
        type="primary" if st.session_state["current_view"] == "Chat" else "secondary",
    ):
        st.session_state["current_view"] = "Chat"
with col2:
    if st.button(
        "Analytics View",
        use_container_width=True,
        type=(
            "primary"
            if st.session_state["current_view"] == "Analytics"
            else "secondary"
        ),
    ):
        st.session_state["current_view"] = "Analytics"

with st.sidebar:
    # Option to choose filtering method (by date range or number of entries)
    filter_option = st.radio(
        "Filter by:", ("Date Range", "Number of Entries", "Custom Date Range")
    )

    if filter_option == "Date Range":
        range_opt = st.selectbox("Range by:", ("Monthly", "Quarterly"))

        if range_opt == "Monthly":
            col1, col2 = st.columns([1, 1])
            with col1:
                Mont = "01"
                Mont = st.radio(
                    "Month:",
                    (
                        "01",
                        "02",
                        "03",
                        "04",
                        "05",
                        "06",
                        "07",
                        "08",
                        "09",
                        "10",
                        "11",
                        "12",
                    ),
                )
            with col2:
                yr = "2023"
                yr = st.radio("Year:", ("2023", "2024", "2025"))
            if Mont == "02":
                start_date = yr + "/" + Mont + "/" + "01"
                end_date = yr + "/" + Mont + "/" + "28"
            elif (
                Mont == "01"
                or Mont == "03"
                or Mont == "05"
                or Mont == "07"
                or Mont == "08"
                or Mont == "10"
                or Mont == "12"
            ):
                start_date = yr + "/" + Mont + "/" + "01"
                end_date = yr + "/" + Mont + "/" + "31"
            else:
                start_date = yr + "/" + Mont + "/" + "01"
                end_date = yr + "/" + Mont + "/" + "30"
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
        res = list(
            container.query_items(query=query_len, enable_cross_partition_query=True)
        )
        num_ent = res[0]
        limit = st.slider(
            "Select the number of entries to fetch",
            min_value=1000,
            max_value=num_ent,
            value=2000,
            step=100,
        )
        start_offset = st.slider(
            "Select the start offset",
            min_value=0,
            max_value=limit,
            value=0,
            step=100,
        )
        start_date = (
            None  # Disable the date range inputs for number of entries filtering
        )
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
            items = list(
                container.query_items(query=query, enable_cross_partition_query=True)
            )

            # Display results
            if items:
                st.write(f"Displaying {len(items)} chat entries:")
                for i in range(len(items)):
                    items[i]["ChatTitle"] = items[i]["ChatTitle"][:50]
                st.session_state["chats"] = list(items)

                chat_titles = [
                    chat["ChatTitle"][:50] for chat in st.session_state["chats"]
                ]
                chat_titles_text = "\n".join(
                    chat_titles
                )  # Join chat titles into a single text block
                st.session_state["topics"] = extract_topics_from_text(chat_titles_text)
                st.session_state["processed_chat_titles"] = preprocess_text(
                    chat_titles_text
                )

                # Get trend analysis
                if chat_titles:
                    with st.spinner("Analyzing trends..."):
                        trend_analysis_response = llmclient.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {
                                    "role": "system",
                                    "content": "You are an expert data analyst analyzing trends from user interaction data.",
                                },
                                {
                                    "role": "user",
                                    "content": f"""
                                    Analyze the following chat titles for trends, topics, and insights based on user interactions. 
                                    Provide a summary of key trends and observations.
                                    
                                    Chat Titles:
                                    {st.session_state["processed_chat_titles"]}
                                """,
                                },
                            ],
                            temperature=0.7,
                            stream=False,  # We want a complete response, not a stream
                        )
                        st.session_state["trend_analysis"] = (
                            trend_analysis_response.choices[0].message.content
                        )
            else:
                st.write("No data found for the selected range.")

        except Exception as e:
            st.write(f"An error occurred: {str(e)}")

    # Display filter information
    if "chats" in st.session_state and st.session_state["chats"]:
        if filter_option == "Date Range":
            st.write(f"Data Range")
            st.write(f"From: {start_date}")
            st.write(f"To: {end_date}")
        elif filter_option == "Custom Date Range":
            st.write(f"Custom Date Range:")
            st.write(f"From: {start_date_str}")
            st.write(f"To: {end_date_str}")
        elif filter_option == "Number of Entries":
            st.write(f"Entries Fetching")
            st.write(f"Limit: {limit}")
            st.write(f"Start Offset: {start_offset}")

# Display Chat View
if st.session_state["current_view"] == "Chat":
    st.markdown(
        '<div class="main-header">Interactive Chat Insights</div>',
        unsafe_allow_html=True,
    )

    # Display trend analysis if available
    if "trend_analysis" in st.session_state and st.session_state["trend_analysis"]:
        st.write("### Trend Analysis")
        st.markdown(st.session_state["trend_analysis"])
        st.write("---")

    # Display previous messages (for chat history)
    for message in st.session_state["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # User input for questions
    if prompt := st.chat_input("Ask a question"):
        # Check if data has been fetched
        if "chats" in st.session_state and st.session_state["chats"]:
            st.session_state["messages"].append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.spinner("Thinking..."):
                response_stream = llmclient.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert product analyst who analyses software products based on the user statistics from user database.",
                        },
                        {
                            "role": "user",
                            "content": f"""
                            Answer the user's prompt based on the following data from the database. 
                            The database contains usage history of user questions and AI responses from an AI-assisted chatbot interface, specifically used for legal advice.

                            User Chat Titles: 
                            {st.session_state["processed_chat_titles"]}
                            Highlighted topics:
                            {st.session_state["topics"]}

                            ---
                            Prompt: {prompt}

                            ---
                            Intelligently analyze the user's intent in the prompt and provide an insightful answer, utilizing relevant data and context from the chat titles.
                            """,
                        },
                    ],
                    temperature=0.7,
                    stream=True,
                )

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                bot_response = ""
                for chunk in response_stream:
                    if chunk.choices:
                        bot_response += chunk.choices[0].delta.content or ""
                        message_placeholder.markdown(bot_response)
            st.session_state["messages"].append(
                {"role": "assistant", "content": bot_response}
            )
        else:
            st.warning("Please fetch data first before asking questions.")

# Display Analytics View
elif st.session_state["current_view"] == "Analytics":
    st.subheader("Quarterly Topic Analysis")

    # Default to last completed year
    current_year = datetime.now().year
    selected_year = st.selectbox(
        "Select Year",
        options=[str(y) for y in range(current_year - 3, current_year + 1)],
        index=2,
    )

    # Define quarterly ranges
    quarters = {
        "Q1": (f"{selected_year}/01/01", f"{selected_year}/03/31"),
        "Q2": (f"{selected_year}/04/01", f"{selected_year}/06/30"),
        "Q3": (f"{selected_year}/07/01", f"{selected_year}/09/30"),
        "Q4": (f"{selected_year}/10/01", f"{selected_year}/12/31"),
    }

    def get_top_topics(start_date, end_date):
        start_date_obj = datetime.strptime(start_date, "%Y/%m/%d")
        end_date_obj = datetime.strptime(end_date, "%Y/%m/%d")
        start_date_str = start_date_obj.strftime("%Y-%m-%dT%H:%M:%S.000000Z")
        end_date_str = end_date_obj.strftime("%Y-%m-%dT%H:%M:%S.000000Z")

        query = f"""
            SELECT c.ChatTitle 
            FROM c 
            WHERE c.TimeStamp BETWEEN '{start_date_str}' AND '{end_date_str}'
            ORDER BY c.TimeStamp DESC
        """
        items = list(
            container.query_items(query=query, enable_cross_partition_query=True)
        )
        chat_titles = "\n".join([item["ChatTitle"][:100] for item in items])

        if not chat_titles.strip():
            return "No data available"

        processed_titles = preprocess_text(chat_titles)

        # LLM call for top 10 topics
        response = llmclient.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a legal domain expert extracting top 10 unique topics from user chat titles. Respond with the list only, no explanation.",
                },
                {
                    "role": "user",
                    "content": f"""
                    From the following user chat titles, identify and list the top 10 unique topics discussed. Do not add any explanation or extra words.

                    Chat Titles:
                    {processed_titles}
                    """,
                },
            ],
            temperature=0.5,
            stream=False,
        )
        return response.choices[0].message.content.strip()

    # Display topics in 4 containers for each quarter
    q1, q2 = st.columns(2)
    q3, q4 = st.columns(2)

    with q1.container(height=500, border=True):
        st.markdown("**Q1 Topics**")
        with st.spinner("Loading Q1 data..."):
            st.write(get_top_topics(*quarters["Q1"]))

    with q2.container(height=500, border=True):
        st.markdown("**Q2 Topics**")
        with st.spinner("Loading Q2 data..."):
            st.write(get_top_topics(*quarters["Q2"]))

    with q3.container(height=500, border=True):
        st.markdown("**Q3 Topics**")
        with st.spinner("Loading Q3 data..."):
            st.write(get_top_topics(*quarters["Q3"]))

    with q4.container(height=500, border=True):
        st.markdown("**Q4 Topics**")
        with st.spinner("Loading Q4 data..."):
            st.write(get_top_topics(*quarters["Q4"]))
