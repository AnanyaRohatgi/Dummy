from flask import Flask, request, jsonify
import fitz  # PyMuPDF
from google.cloud import storage
import uuid

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle_webhook():
    req = request.get_json()
    user_query = req.get("query", "").lower()

    bucket_name = "dummybot-chatbot-images"
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    response = []
    for blob in bucket.list_blobs():
        if blob.name.endswith(".pdf"):
            pdf_data = blob.download_as_bytes()
            doc = fitz.open(stream=pdf_data, filetype="pdf")

            for page in doc:
                text = page.get_text()
                if user_query in text.lower():
                    entry = {
                        "document": blob.name,
                        "text": text.strip(),
                        "images": []
                    }

                    for img in page.get_images(full=True):
                        xref = img[0]
                        image = doc.extract_image(xref)
                        img_bytes = image["image"]
                        ext = image["ext"]

                        image_name = f"temp_images/{uuid.uuid4()}.{ext}"
                        image_blob = bucket.blob(image_name)
                        image_blob.upload_from_string(img_bytes, content_type=f"image/{ext}")
                        image_blob.make_public()
                        entry["images"].append(image_blob.public_url)

                    response.append(entry)
                    break

    if not response:
        return jsonify({"fulfillment_response": {"messages": [{"text": {"text": ["No match found."]}}]}})

    messages = []
    for r in response:
        messages.append({"text": {"text": [f"📄 {r['document']}\n{r['text'][:300]}"]}})
        for img_url in r["images"]:
            messages.append({
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

    return jsonify({"fulfillment_response": {"messages": messages}})
