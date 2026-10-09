**Retrieval Log** shows, for every chat turn, the candidate passages retrieval considered, their
relevance scores, and which ones actually reached the final answer — useful for understanding
*why* an answer cited what it did, or why it missed something you expected. Queries themselves are
stored only as a hash, never as plain text.

**Retrieval Settings** tunes how retrieval behaves for your workspace: how many results feed an
answer, and the minimum relevance score a passage needs to be considered. Leaving a field blank
keeps the platform-wide default (shown as its placeholder); changes apply within about 30 seconds,
no restart required.

![Retrieval log entry showing scored candidates](/docs/images/retrieval-log.png)
