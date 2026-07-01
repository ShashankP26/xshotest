import os

template_dir = '/Users/shashank/Downloads/xshottest/xshot/xshot/gstbillingapp/templates/gstbillingapp/'
files_to_fix = [
    'credit_notes.html',
    'credit_note_printer.html',
    'credit_note_edit.html'
]

for file_name in files_to_fix:
    path = os.path.join(template_dir, file_name)
    with open(path, 'r') as f:
        content = f.read()
        
    content = content.replace("credit_note.invoice_", "credit_note.credit_note_")
    
    with open(path, 'w') as f:
        f.write(content)

print("Templates fixed.")
