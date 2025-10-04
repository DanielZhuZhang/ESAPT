import os
file_path = "../Spider Dataset(Clean)"
for dirpath, dirnames, filenames in os.walk(file_path):
    for filename in filenames:
        if filename == "schema.drawio":
            os.remove(os.path.join(dirpath, filename))