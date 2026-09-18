import pymupdf

doc = pymupdf.open(r'Project_Requirements.pdf')
print(f'Total pages: {doc.page_count}')
all_text = []
for i, page in enumerate(doc):
    text = page.get_text()
    all_text.append(f'\n=== PAGE {i+1} ===\n{text}')

full_text = '\n'.join(all_text)
with open('prd_extracted.txt', 'w', encoding='utf-8') as f:
    f.write(full_text)
print('Extraction complete. Saved to prd_extracted.txt')
doc.close()
