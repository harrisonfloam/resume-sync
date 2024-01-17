# resume-sync

A Python script that syncs files between Google Drive and Dropbox based on standardized naming conventions. Designed for execution using GitHub Actions.

Currently only configured for my personal account, but may refactor for other users in the future.

| ![image](https://github.com/harrisonfloam/resume-sync/assets/130672912/c5b8c246-acd8-489a-aa9d-826409732344) |
| :--: |
| *Example workflow execution in GitHub Actions* |

### Motivation

I am currently in the middle of a job search, and found myself struggling to source control many versions of my resume and maintain updated PDF copies for sharing. For ease of editing, I work in Google Drive, which offers a unique problem set:

1. PDF conversion: I like to send resumes in PDF format, but converting documents to PDF in Google Drive is a multi-step process.
2. Accessibility: While Google Drive is accessible on most platforms, it has limited compatibility with iOS devices. Notably, it is impossible to save a Google Document as a PDF from iOS, making it impossible for me to retrieve an updated resume when mobile. Dropbox is a much nicer alternative that works natively with iOS automation methods, and is commonly available for resume submission when applying online.
3. Version control: Managing my resume versioning manually gave me a headache.

### Workflow

This workflow is configured to run in GitHub actions on a schedule (cron) trigger as well as a manual dispatch trigger. I can trigger a manual dispatch from my iPhone via shortcut, using the GitHub app's pre-built shortcut methods. It executes in around 30s, depending on runner availability.

1. Authenticate Google Drive and Dropbox credentials stored in GitHub Secrets. Error or expired tokens will require local execution to re-authenticate via OAuth2 flow.
2. Download PDF copies of resumes modified in the past week from Google Drive. Downloaded PDFs are temporarily stored in the working directory, under /temp_pdf, until the workflow is complete. Original directory structure is maintained, allowing subfolders in Google Drive for targeted resumes, cover letter, etc.
3. Upload each downloaded PDF to Dropbox, maintaining the original directory structure.
4. Match filenames and date strings on updated resumes with those currently in Dropbox and delete older versions of the same resume.
5. Delete contents of /temp_pdf.



