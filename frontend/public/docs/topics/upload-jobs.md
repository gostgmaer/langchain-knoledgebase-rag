Every document upload runs through a pipeline — queued, then running, then succeeded or failed —
and Upload Jobs shows that progress in real time. The list shows each job's file name, status,
error (if it failed), and when it started, finished, and was created.

Paste a specific `upload_job_id` (a UUID) into **Look up** to jump straight to one job's full
detail — file name, status, the document it produced (once one exists), its error if any, and
start/finish times — useful when a user reports a stuck or failed upload and gives you its id
directly, rather than hunting for it in the list.

![Upload job progressing through its pipeline stages](/docs/images/upload-jobs.png)
