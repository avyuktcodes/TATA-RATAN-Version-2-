import os
from pypdf import PdfReader, PdfWriter

input_pdf = "./data/tatasteel-iar-2025-26.pdf"
output_dir = "./data_split_10"
chunk_size = 10  # pages per chunk

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

reader = PdfReader(input_pdf)
total_pages = len(reader.pages)
print(f"Total pages: {total_pages}")

for i in range(0, total_pages, chunk_size):
    writer = PdfWriter()
    end = min(i + chunk_size, total_pages)
    
    for j in range(i, end):
        writer.add_page(reader.pages[j])
        
    output_path = os.path.join(output_dir, f"part_{i // chunk_size + 1}.pdf")
    with open(output_path, "wb") as f:
        writer.write(f)

print("SUCCESS! PDF has been split into 10-page chunks.")
