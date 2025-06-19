import os
import streamlit as st
from dotenv import load_dotenv


# Load environment variables early
load_dotenv()

# Ensure OPENAI_API_KEY is set in environment before importing LangChain
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

import pyodbc
import openai
from dynamic_sql_generation import generate_sql_from_nl
from dynamic_sql_generation import select_prompt
import re
import contractions

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DRIVER = os.getenv("Driver")
SERVER = os.getenv("Server")
DATABASE = os.getenv("Database")
UID = os.getenv("UID")
PWD = os.getenv("PWD")

openai.api_key = OPENAI_API_KEY

import re

def validate_sql_query(sql_query):
    # Step 0: Clean leading SQL-like prefixes (e.g., "SQL:", "```sql", etc.)
    sql_query = sql_query.strip()
    sql_query = re.sub(r"^\s*(SQL:?|```sql)?\s*", "", sql_query, flags=re.IGNORECASE)

    # Optional: remove trailing ``` block or semicolon
    sql_query = re.sub(r"```$", "", sql_query).strip()
    sql_query = sql_query.rstrip(";").strip()

    # Step 1: Check for placeholder or example values in the SQL query
    placeholders = ['specific_salesofficeid', 'example_value', 'placeholder']
    for ph in placeholders:
        if ph.lower() in sql_query.lower():
            return False, f"SQL query contains placeholder value: {ph}"

    return True, ""


def execute_sql_query(sql_query):
    try:
        connection_string = (
            f"DRIVER={{{DRIVER}}};"
            f"SERVER={SERVER};"
            f"DATABASE={DATABASE};"
            f"UID={UID};"
            f"PWD={PWD}"
        )
        with pyodbc.connect(connection_string, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(sql_query)
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            results = [dict(zip(columns, row)) for row in rows]
            return results
    except Exception:
        st.error("There’s a server-side issue right now. Please restart your HFL server. it’s currently unable to fetch data due to heavy load. Thanks for your patience")
        return None

import re
import openai
import streamlit as st

from decimal import Decimal


import streamlit as st
import pandas as pd
import plotly.express as px

import plotly.express as px
import requests
import json
from io import BytesIO
from PIL import Image as PILImage
import matplotlib.pyplot as plt

def format_results_as_graph(results, title="Graph from Results"):
    """
    Elegant graph generator from SQL results.
    Automatically uses Plotly or QuickChart.io if Plotly fails or isn't supported.
    """
    if not results:
        raise ValueError("Empty results received")

    df = pd.DataFrame(results)
    if df.empty:
        raise ValueError("DataFrame is empty after conversion")

    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    text_cols = df.select_dtypes(include='object').columns.tolist()
    col_names = [col.lower() for col in df.columns]

    colors = px.colors.qualitative.Safe
    sales_keywords = {"sales", "salesquantity", "volume", "salequantity", "quantity"}
    budget_keywords = {"actual", "target", "achievement", "achievementpercent"}

    try:
        # Plotly-Based Graphs
        if budget_keywords.intersection(col_names):
            y_cols = [col for col in df.columns if col.lower() in budget_keywords]
            x_candidates = [col for col in df.columns if col not in y_cols]
            if x_candidates:
                x_col = x_candidates[0]
                fig = px.bar(df, x=x_col, y=y_cols, title=title, barmode="group", text_auto='.2f', color_discrete_sequence=colors)
            else:
                df_melted = df[y_cols].melt(var_name="Metric", value_name="Value")
                fig = px.bar(df_melted, x="Metric", y="Value", title=title, text_auto='.2f', color_discrete_sequence=colors)

        elif any("date" in col for col in col_names) and any(kw in col_names for kw in sales_keywords):
            date_col = next((col for col in df.columns if "date" in col.lower()), df.columns[0])
            sales_cols = [col for col in df.columns if col.lower() in sales_keywords]
            fig = px.line(df, x=date_col, y=sales_cols, title=title, markers=True, color_discrete_sequence=colors)

        elif len(text_cols) >= 1 and len(numeric_cols) >= 1:
            fig = px.bar(df, x=text_cols[0], y=numeric_cols, title=title, barmode="group", text_auto='.2f', color_discrete_sequence=colors)

        elif len(numeric_cols) == 1:
            fig = px.histogram(df, x=numeric_cols[0], title=title, color_discrete_sequence=colors)

        elif len(numeric_cols) > 1:
            df_melted = df[numeric_cols].melt(var_name="Metric", value_name="Value")
            fig = px.bar(df_melted, x="Metric", y="Value", title=title, text_auto='.2f', color_discrete_sequence=colors)

        else:
            raise ValueError("Unable to determine chart structure.")

        fig.update_layout(
            title_x=0.5,
            bargap=0.3,
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(size=13, family="Arial"),
            xaxis=dict(showticklabels=True, title='', showgrid=False, ticks='', linecolor='rgba(0,0,0,0.15)'),
            yaxis=dict(showticklabels=False, title='', showgrid=False, ticks='', linecolor='rgba(0,0,0,0.15)'),
            margin=dict(t=60, l=40, r=40, b=50),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
        )

        return fig

    except Exception as e:
        # Fallback to QuickChart
        if len(text_cols) >= 1 and len(numeric_cols) >= 1:
            chart_config = {
                "type": "bar",
                "data": {
                    "labels": df[text_cols[0]].tolist(),
                    "datasets": [{
                        "label": numeric_cols[0],
                        "data": df[numeric_cols[0]].tolist()
                    }]
                },
                "options": {
                    "title": {"display": True, "text": title},
                    "plugins": {
                        "legend": {"display": False}
                    },
                    "scales": {
                        "y": {"ticks": {"display": False}},
                        "x": {"ticks": {"font": {"size": 12}}}
                    }
                }
            }
            quickchart_url = "https://quickchart.io/chart"
            response = requests.get(quickchart_url, params={"c": json.dumps(chart_config)})

            # Render using PIL or Matplotlib (optional, for environments like Streamlit)
            img = PILImage.open(BytesIO(response.content))
            plt.imshow(img)
            plt.axis('off')
            plt.title(title)
            plt.show()
        else:
            raise ValueError("Graph rendering failed. Check data format or column types.")

def format_results_as_html_table(results):
    # Start the table
    html_table = "<div style='overflow-x: auto;'><table style='width: 100%; border-collapse: collapse; font-size: 12px;'>"
    
    # Add header row (include S. No.)
    headers = ["S. No."] + list(results[0].keys())  # Add "S. No." to headers
    html_table += "<thead><tr>"
    for header in headers:
        html_table += f"<th style='border: 1px solid #ddd; padding: 4px; text-align: left;'>{header}</th>"
    html_table += "</tr></thead>"

    # Add rows with serial number
    html_table += "<tbody>"
    for idx, row in enumerate(results, start=1):  # Start indexing from 1
        html_table += "<tr>"
        html_table += f"<td style='border: 1px solid #ddd; padding: 4px; text-align: left;'>{idx}</td>"  # Add serial number
        for value in row.values():
            formatted_value = str(value)
            html_table += f"<td style='border: 1px solid #ddd; padding: 4px; text-align: left;'>{formatted_value}</td>"
        html_table += "</tr>"
    html_table += "</tbody>"

    # End the table
    html_table += "</table></div>"

    return html_table


#def format_sql_results(results):
    formatted_rows = []
    for row in results:
        formatted_row = {}
        for key, value in row.items():
            if isinstance(value, (float, int, Decimal)):
                formatted_value = f"{float(value):,.2f}"  # 2 decimal places with commas
            else:
                formatted_value = str(value)
            formatted_row[key] = formatted_value
        formatted_rows.append(formatted_row)
    return formatted_rows

def format_sql_results(results, user_query):
    formatted_rows = []
    user_query_lower = user_query.lower()
    ubc_mode = "ubc" in user_query_lower or "unique billing count" in user_query_lower

    for row in results:
        formatted_row = {}
        for key, value in row.items():
            if isinstance(value, (float, int, Decimal)):
                value_float = float(value)
                if ubc_mode and value_float.is_integer():
                    formatted_value = f"{int(value_float):,}"  # drop .00 for whole numbers
                else:
                    formatted_value = f"{value_float:,.2f}"  # keep 2 decimals
            else:
                formatted_value = str(value)
            formatted_row[key] = formatted_value
        formatted_rows.append(formatted_row)
    
    return formatted_rows

def results_to_natural_language(results, user_query):
    print(results)
    if not results:
        return "Please wait."
    formatted_results= format_sql_results(results,user_query)
    print(formatted_results)

    # System prompt to reduce typos and ensure clear output
    system_prompt = (
"You are a highly accurate summarization assistant specialized in converting SQL output into plain  English. Your job is to reflect **only** the terms from the **user query** and the **SQL output**."
    "Your job is to report exactly what is present in the SQL result without changing any values, names, or formats.\n"
    "Strictly follow these rules:\n"
    "- Always display all rows and all columns shown in the result — do not skip anything.\n"
    "- Never paraphrase, abbreviate, or rename columns or values — copy them as-is.\n"
    "- Never explain how the values were calculated — just summarize what is shown.\n"
    "- Format all decimal numbers to exactly 2 digits after the decimal point (e.g., 101.137 → 101.14, 101 → 101.00).\n"
    "- Emojis are optional (📈, ↑, %, etc.) if they match the context.\n"
    "Don't include irrelevant currency symbols."
    "Strict: if you found the *sale* or *volume*  in user query then you has to refer as *sale quantity* and never use total infont of that\n"
    " strict : if you found that *actual* or *target* in user query then you has add *qunatity* word beside those\n"
)

    prompt_text = (
    f"User query: \"{user_query}\"\n\n"
    f"SQL result:\n{formatted_results}\n\n"
"Write a clear and very simple English summary based **only** on the values above. Ensure the summary is meaningful by directly relating it to the user's original query. Do not introduce any new terms — use only the words from the SQL result and user query."
    "- Use all column values and rows without skipping any.\n"
    "- Do not interpret or explain calculations.\n"
    "- Do not abbreviate or rename anything.\n"
    "- Format all decimal numbers to 2 decimal places exactly (e.g., 101.137 → 101.14, 101 → 101.00).\n"
    "Don't include irrelevant currency symbols."
    "Strict: if you found the *sale* or *volume*  in user query then you has to refer as *sale quantity* and never use total infont of that\n"
    " if you found that *actual* or *target* or *budget* in user query then you has add *qunatity* word beside those\n"
    "Strict: if you found the *sale* or *volume*  in user query then you has to refer as *sale quantity* and never use total infont of that\n"
    "dont introduce new terms "
    "if user asked the tabular format means you has to display in table "
    "Summary:"
)
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_text}
            ],
            max_tokens=500,
            temperature=0.1,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
        )
        summary = response.choices[0].message['content'].strip()
        return summary

    except Exception as e:
        return f"Error generating summary: {e}"

custom_stop_words = {
    'rushi' 
}
def remove_custom_stop_words(query, stop_words):
    tokens = query.lower().split()  # lowercase + split
    filtered = [word for word in tokens if word not in stop_words]
    return " ".join(filtered)

def main():
    st.set_page_config(page_title="AskHFL", page_icon="🗄️", layout="centered")

    st.markdown("""
    <div style="
        background-color: #28a745;
        padding: 1px;
        border-radius: 8px;
        text-align: center;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    ">
        <h2 style="
            color: white;
            font-family: 'Segoe UI', 'Roboto', sans-serif;
            font-weight: 600;
            margin: 0;
            font-size: 28px;
        ">
             Ask Heritage
        </h2>
    </div>
""", unsafe_allow_html=True)

    user_query = st.text_area("Enter your query:", height=70)

    sql_query = None  # Initialize sql_query to avoid UnboundLocalError

    if st.button("Run Query"):
        if not user_query.strip():
            st.warning("Please enter a query.")
            return

        with st.spinner("Translating to SQL..."):
            preprocessed_query = remove_custom_stop_words(user_query, custom_stop_words)

        # Generate SQL from preprocessed query
        sql_query = generate_sql_from_nl(preprocessed_query)

        # Fix SQL value quoting based on column types and other fixes
        #sql_query = fix_sql_value_quoting(sql_query)

        print(f"Generated SQL Query: {sql_query}")

    # Validate SQL query for placeholders
    if sql_query is None:
        st.warning("hey, how can i assist you?")
        return

    valid, error_msg = validate_sql_query(sql_query)
    if not valid:
        st.error(error_msg)
        return

    with st.spinner("Executing..please wait searching in you database."):
        try:
            results = execute_sql_query(sql_query)
        except Exception:
            st.error("There’s a server-side issue right now. Please restart your HFL server. it’s currently unable to fetch data due to heavy load. Thanks for your patience")
            return

    if results is not None:
        # Check if the query asks for a table format
        if "table format" in user_query.lower() or "tabular" in user_query.lower() or "table" in user_query.lower():
            # Convert results into HTML table format
            html_table = format_results_as_html_table(results)
            st.markdown(html_table, unsafe_allow_html=True)
        if "graph" in user_query.lower():
            fig = format_results_as_graph(results)
            st.plotly_chart(fig, use_container_width=True)
        else:
            summary = results_to_natural_language(results, user_query)
            summary = re.sub(r'[\$]', '', summary)
            summary = re.sub(r'\bamount\b', 'Amount in Rupees', summary, flags=re.IGNORECASE)
            summary = re.sub(r'(\b(?:count|ubc)\b[^.]*?)\b([\d,]+)\.00\b', r'\1\2', summary, flags=re.IGNORECASE)

            print("The result from the llm: ", summary)
            st.markdown(f"""
    <div style="
        background: transparent;
        padding: 20px 15px;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        font-size: 16px;
        line-height: 1.5;
        max-width: 800px;
        border-radius: 8px;
        font-weight: 600;           
        border: 1px solid rgba(204, 204, 204, 0.13);
    ">
    <h4 style="margin-bottom: 12px; font-weight: 600;"> 
         Your query result 🧾:
        </h4>
        <p style="white-space: pre-line;">{summary}</p>
    </div>
    """, unsafe_allow_html=True)
       
if __name__ == "__main__":
    main()
