from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import NMF
import logging
import re
import json
import os
from openai import AzureOpenAI
from preprocessor import preprocess_text


# Initialize Azure OpenAI client
llmclient = AzureOpenAI(
    azure_endpoint=os.getenv("LLM_ENDPOINT"),
    api_key=os.getenv("LLM_KEY"),
    api_version="2024-10-01-preview",
)


def extract_topics_from_text(text, max_topics=5, max_top_words=10):
    """Extract topics using NMF and return structured topic data in JSON format."""
    try:
        cleaned_text = preprocess_text(text)
        if len(cleaned_text.split()) < 10:
            logging.warning("Text too short for meaningful topic extraction")
            return []

        vectorizer = TfidfVectorizer(
            stop_words="english",
            max_df=0.85,
            min_df=2,
            ngram_range=(1, 2),
            max_features=1000,
        )

        # Split text into sentences or chunks
        sentences = text.split(".")
        if len(sentences) < 3:
            sentences = [
                text[i : i + 100]
                for i in range(0, len(text), 100)
                if len(text[i : i + 100].strip()) > 0
            ]

        tfidf = vectorizer.fit_transform(sentences)

        if tfidf.shape[1] < 2:
            logging.warning("Not enough features extracted for NMF")
            return []

        n_topics = min(max_topics, min(5, tfidf.shape[1] - 1))

        nmf = NMF(n_components=n_topics, random_state=42, max_iter=500, l1_ratio=0.5)

        nmf_result = nmf.fit_transform(tfidf)
        feature_names = vectorizer.get_feature_names_out()

        topics = []
        for topic_idx, topic in enumerate(nmf.components_):
            top_features_ind = topic.argsort()[: -max_top_words - 1 : -1]
            top_features = [feature_names[i] for i in top_features_ind]

            weights = topic[top_features_ind]
            weights = weights / weights.sum()

            weighted_terms = [
                {"term": feature, "weight": float(weight)}
                for feature, weight in zip(top_features, weights)
            ]

            topics.append(
                {
                    "topic": f"Topic {topic_idx + 1}",
                    "score": float(sum(weights)),
                    "keywords": weighted_terms,
                }
            )

        topic_analysis = ""
        for topic_item in topics:
            topic_analysis += (
                f"Topic {topic_item['topic']} (score: {topic_item['score']:.2f}):\n"
            )
            for keyword in topic_item["keywords"]:
                topic_analysis += (
                    f"- {keyword['term']} (weight: {keyword['weight']:.2f})\n"
                )

        return interpret_topics_with_llm(text, topic_analysis)

    except Exception as e:
        logging.error(f"Error extracting topics: {e}")
        return []


def interpret_topics_with_llm(text, raw_topics):
    """
    Use LLM to interpret raw topics and return structured interpretations in JSON format.
    """
    try:
        prompt = f"""
        Analyze the following text and the extracted topic keywords to identify the main themes and topics.

        Text excerpt: {text[:1000]}... (truncated for brevity)
        
        Raw extracted topics:
        {raw_topics}
        
        Return a JSON array of topic objects with the following structure:
        [
            {{
                "label": "Clear topic name",
                "description": "Brief 1-2 sentence description of the topic"
            }},
            ...
        ]
        
        Ensure your response can be parsed as valid JSON. Return ONLY the JSON array and nothing else.
        """

        response = llmclient.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a topic analysis expert who can identify meaningful themes and topics from text and return them in valid JSON format.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        interpreted_content = response.choices[0].message.content

        # Try to parse the response as JSON
        try:
            parsed_topics = json.loads(interpreted_content)
            return parsed_topics
        except json.JSONDecodeError:
            # If direct parsing fails, try to extract JSON from the response
            json_pattern = r"\[[\s\S]*\]"
            match = re.search(json_pattern, interpreted_content)
            if match:
                try:
                    json_str = match.group(0)
                    parsed_topics = json.loads(json_str)
                    return parsed_topics
                except json.JSONDecodeError:
                    pass

            # Fallback: return a basic structure with the raw content
            logging.warning(
                "Failed to parse LLM response as JSON, returning raw content"
            )
            return [{"label": "Topic analysis", "description": interpreted_content}]

    except Exception as e:
        logging.error(f"Error interpreting topics with LLM: {e}")
        return []
