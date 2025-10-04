import subprocess
import os

def convert_drawio_to_png(input_file, output_file):
    subprocess.run([
        r"C:\Program Files\draw.io\draw.io.exe",
        "--export",
        "--format", "png",
        "--output", output_file,
        input_file
    ])
print(os.getcwd())
convert_drawio_to_png("../Spider Dataset(Clean)/Daniel/apartment_rentals/apartment_rentals(SQLtoERD).drawio", "diagram.png")

file_path = "../Spider Dataset(Clean)"

