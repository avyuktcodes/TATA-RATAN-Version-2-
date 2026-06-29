from pypdf import PdfReader, PdfWriter

# Point to your massive PDF
reader = PdfReader("./data/tatasteel-iar-2025-26.pdf")
writer = PdfWriter()

# Extract just the first 5 pages (index 0 through 4)
for i in range(5):
    writer.add_page(reader.pages[i])

# Save it to your new mini folder
with open("./data_mini/subset.pdf", "wb") as f:
    writer.write(f)

print("SUCCESS! subset.pdf has been created in ./data_mini")