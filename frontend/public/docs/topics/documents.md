Documents are files uploaded directly, rather than discovered through a Knowledge Source. Drop a
file on **Documents** to upload it; Meridian loads it, cleans it, splits it into chunks, embeds
those chunks, and indexes them — the same pipeline a connector's content goes through, just
triggered by an upload instead of a sync. Track an upload still in progress on the
[Upload Jobs](/docs/upload-jobs) page.

The list shows, per document: its name (linking to its detail page and version history), badges for
where it came from (a knowledge source name, if it wasn't a direct upload), **admins only**
visibility when restricted, document type/category/tags, processing **status**, chunking strategy,
chunk count, whether this is the **current** version or a **superseded** one, size, and when it was
uploaded. Re-uploading the same document creates a new version rather than silently overwriting the
old one — the version history icon jumps straight to it. **Delete** removes a document from the
search index entirely, after a confirmation.

![Documents list with upload in progress](/docs/images/documents-list.png)
