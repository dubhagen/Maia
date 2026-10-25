# web_fetch - Web Fetch

Fetch the content of an HTTP/HTTPS URL. Web pages are extracted as readable text; document files (PDF, Word, Excel, etc.) are downloaded and parsed automatically.

## Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `url` | string | Yes | HTTP/HTTPS URL (web page or document) |

## Supported file types

| Type | Formats |
| --- | --- |
| PDF | `.pdf` |
| Word | `.docx` |
| Text | `.txt`, `.md`, `.csv`, `.log` |
| Spreadsheet | `.xls`, `.xlsx` |
| Presentation | `.ppt`, `.pptx` |

## Use cases

- Extract readable text from a web page
- Download and parse remote documents
- Inspect API response bodies

`web_fetch` downloads the URL itself. It does not call a hosted fetch API.
The SSRF guard still applies: private, loopback, and cloud-metadata URLs
are rejected before any request is issued. Document URLs (PDF, Word, etc.)
are downloaded and parsed locally.

> **Note.** `web_fetch` only retrieves static HTML. For pages that require JavaScript rendering (such as SPAs), use the `browser` tool instead.
