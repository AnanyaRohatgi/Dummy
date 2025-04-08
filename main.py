import functions_framework
from google.cloud import storage
import fitz  # PyMuPDF
import json
import uuid

@functions_framework.http
def extract_text_images(request):
    request_json = request.get_json(silent=True)
    user_query = request_json.get("query", "").lower()

    if not user_query:
        return ("Missing 'query' in request", 400)

    bucket_name = "dummybot-chatbot-images"
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    response = []
    img_counter = 0

    for blob in bucket.list_blobs():
        if blob.name.endswith(".pdf"):
            pdf_data = blob.download_as_bytes()
            doc = fitz.open(stream=pdf_data, filetype="pdf")

            for page_num, page in enumerate(doc):
                text = page.get_text()
                if user_query in text.lower():
                    entry = {
                        "document": blob.name,
                        "page": page_num + 1,
                        "text": text.strip(),
                        "images": []
                    }

                    images = page.get_images(full=True)
                    for img_index, img in enumerate(images):
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]

                        img_blob_name = f"temp_images/{uuid.uuid4()}.{image_ext}"
                        img_blob = bucket.blob(img_blob_name)
                        img_blob.upload_from_string(image_bytes, content_type=f"image/{image_ext}")
                        img_blob.make_public()  # Allow public access

                        entry["images"].append(img_blob.public_url)
                        img_counter += 1

                    response.append(entry)
                    break  # move to next file after first match

    if not response:
        response_text = "Sorry! I couldn't find anything relevant in the documents."
        return json.dumps({
            "fulfillment_response": {
                "messages": [{"text": {"text": [response_text]}}]
            }
        }), 200, {'Content-Type': 'application/json'}

    # Format response nicely for Dialogflow
    final_messages = []
    for r in response:
        msg = f"📄 **{r['document']}** (Page {r['page']}):\n{r['text'][:500]}"
        final_messages.append({"text": {"text": [msg]}})

        for img_url in r["images"]:
            final_messages.append({
                "payload": {
                    "richContent": [[
                        {
                            "type": "image",
                            "rawUrl": img_url,
                            "accessibilityText": "Extracted image"
                        }
                    ]]
                }
            })

    return json.dumps({
        "fulfillment_response": {
            "messages": final_messages
        }
    }), 200, {'Content-Type': 'application/json'}
