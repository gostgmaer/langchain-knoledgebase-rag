Documents are files uploaded directly, rather than discovered through a Knowledge Source. Drop a
file on **Documents** to upload it; Meridian loads it, cleans it, splits it into chunks, embeds
those chunks, and indexes them — the same pipeline a connector's content goes through, just
triggered by an upload instead of a sync.

A document's detail page shows its metadata, processing status, and version history (re-uploading
the same document creates a new version rather than silently overwriting the old one). Track an
upload still in progress on the [Upload Jobs](/docs/upload-jobs) page.

![Documents list with upload in progress](/docs/images/documents-list.png)
