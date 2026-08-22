# Data directory

Put the five KoboToolbox exports here for a local/private deployment:

- `Enterprise*.xlsx`
- `Location*.xlsx`
- `*Residents*.xlsx`
- `Workers*.xlsx`
- `Tourist*.xlsx`

**Privacy:** these are fieldwork survey exports. Do not commit raw respondent-level files to a public GitHub repository. For a public demo, use synthetic/anonymized data or deploy the app from a private repository/data store.

The application also supports `APP_DATA_DIR` so the data can live outside the repository.
