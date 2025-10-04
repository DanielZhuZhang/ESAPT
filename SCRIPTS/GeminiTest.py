import os
import re
from google import genai

client = genai.Client(api_key="AIzaSyCRBP9yA8mavdaepsouEfpElGCnUIOu4_M")

myfile = client.files.upload(file="../Spider Dataset(Clean)/Daniel/apartment_rentals/diagram.png")

response = client.models.generate_content(
    model="gemini-2.5-flash", contents=["can you see this file", myfile]
)

print(response.text)