from weasyprint import HTML

HTML('http://example.com').write_pdf('/tmp/test.pdf')
