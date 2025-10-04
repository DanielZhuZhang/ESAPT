import os
import re
from google import genai
from common.config import instruction
client = genai.Client(api_key="AIzaSyCRBP9yA8mavdaepsouEfpElGCnUIOu4_M")

spider_dataset_path = "../Spider Dataset(Clean)"
for dirpath, dirnames, filenames in os.walk(spider_dataset_path):
    for filename in filenames:
        if filename == "diagram.png":
            #file_path = os.path.join(dirpath, filename)
            #print(f"Processing {file_path}...")

            uploaded = client.files.upload(file="diagram.png")

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[instruction, uploaded],
            )

            text = response.text or ""

            # Save SQL to file
            base_name = os.path.splitext(filename)[0]
            #sql_path = os.path.join(dirpath, f"LLM generated SQL.sql")
            with open("LLM generated SQL.sql", "w", encoding="utf-8") as f:
                f.write(text)

            print(f"Saved SQL for {filename} → LLM")
