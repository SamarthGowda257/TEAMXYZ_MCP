# Hospital documents for the knowledge base (RAG)

Put the real hospital documents here as Markdown (`.md`) or plain text (`.txt`): policies, visitor rules, FAQs,
department pages, price lists. On every server start and every `/ops/reset-demo` the server:

1. splits each file into passages: one per `## Heading` section, split again at sentence ends if a section is longer
   than about 700 characters;
2. stores them in Postgres (`search_docs`, kind `kb`, ref `kb:doc:<file>:<heading>`) for keyword, typo and meaning
   search, and gives each one a Gemini embedding in the background (cached, so restarts cost nothing);
3. refreshes the hospital profile on the Redis blackboard and starts a fresh answer cache.

`get_hospital_info` (Info agent) then answers from them. Each passage is read out as the answer, so write every
section as 1 to 4 plain sentences a receptionist could say: no tables, no bullet lists, no links.

Example file `visitor-policy.md`:

    ## Visiting hours
    Ward visiting hours are 11 AM to 1 PM and 5 PM to 7 PM, two visitors at a time.

    ## Children visiting
    Children under 12 may visit general wards with an adult, but not the ICU.

Check what is loaded: `/api/ops/kb?token=<DASHBOARD_TOKEN>` (add `&kind=doc` for your files only, `&full=true` for
whole texts). This README is not loaded.
