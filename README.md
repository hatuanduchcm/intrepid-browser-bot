Intrepid Invoice Sync

Scaffold for syncing invoice adjustments from the embedded Intrepid app.

Structure:
- requirements.txt : Python deps
- main.py : entrypoint + InvoiceSyncBot class

Quick start:
```powershell
python -m pip install -r requirements.txt
python -m main
```

Next steps:
- Decide whether to attach to embedded browser (remote-debugging) or use UI automation.
- Provide credentials and the target workflow (pages, selectors, and actions).
