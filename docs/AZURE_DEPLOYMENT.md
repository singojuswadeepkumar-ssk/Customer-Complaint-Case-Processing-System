# Deploying to Azure (Container Instance, no web UI required)

Your app is a **batch job**, not a web service: it reads files from `data/`,
calls Gemini, and writes results to `output/`, then exits. This guide deploys
it exactly that way in Azure — no HTTP server, no public URL, no UI.

You will use **3 Azure services**:

| Service | Purpose | Analogue on your PC |
|---|---|---|
| Azure Container Registry (ACR) | Stores your Docker image | Like a private Docker Hub |
| Azure File Share | Persistent storage for `data/` and `output/` | Like a shared network drive |
| Azure Container Instance (ACI) | Runs the container once, then stops | Like double-clicking `main.py` on a cloud VM |

You interact with all of this via the **Azure CLI** (`az` commands) from your
own terminal — no portal clicking required, though the portal works too.

---

## Prerequisites (one-time setup)

1. Install the Azure CLI: https://learn.microsoft.com/cli/azure/install-azure-cli-windows
2. Install Docker Desktop: https://www.docker.com/products/docker-desktop/
3. Log in:
   ```powershell
   az login
   ```
4. Pick names (must be globally unique for some resources) and set variables
   for this session:
   ```powershell
   $RG        = "complaint-processor-rg"
   $LOCATION  = "eastus"
   $ACR_NAME  = "complaintprocessoracr123"     # must be globally unique, lowercase, no dashes
   $STORAGE   = "complaintprocessorst123"      # must be globally unique, lowercase
   $SHARE     = "complaint-data"
   $CONTAINER = "complaint-processor"
   ```

---

## Step 1 — Create a Resource Group

A resource group is just a folder that holds all the Azure resources for this
project so you can manage/delete them together.

```powershell
az group create --name $RG --location $LOCATION
```

## Step 2 — Create the Container Registry and push your image

```powershell
az acr create --resource-group $RG --name $ACR_NAME --sku Basic
az acr login --name $ACR_NAME

# Build the image locally (from the project root, where the Dockerfile is)
docker build -t "$ACR_NAME.azurecr.io/complaint-processor:latest" .

# Push it to Azure
docker push "$ACR_NAME.azurecr.io/complaint-processor:latest"
```

## Step 3 — Create an Azure File Share (this replaces your local data/ and output/ folders)

```powershell
az storage account create --resource-group $RG --name $STORAGE --sku Standard_LRS
$STORAGE_KEY = az storage account keys list --resource-group $RG --account-name $STORAGE --query "[0].value" -o tsv

az storage share create --account-name $STORAGE --account-key $STORAGE_KEY --name $SHARE
```

Upload your complaint documents to the share (equivalent of copying files
into your local `data/` folder):

```powershell
az storage directory create --account-name $STORAGE --account-key $STORAGE_KEY --share-name $SHARE --name data
az storage directory create --account-name $STORAGE --account-key $STORAGE_KEY --share-name $SHARE --name output

az storage file upload --account-name $STORAGE --account-key $STORAGE_KEY --share-name $SHARE `
    --source ".\data\complaint_001_billing.txt" --path "data/complaint_001_billing.txt"
# repeat for each file you want to process
```

## Step 4 — Run the container (this is your "deploy")

```powershell
$ACR_PASSWORD = az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv

az container create `
  --resource-group $RG `
  --name $CONTAINER `
  --image "$ACR_NAME.azurecr.io/complaint-processor:latest" `
  --registry-login-server "$ACR_NAME.azurecr.io" `
  --registry-username $ACR_NAME `
  --registry-password $ACR_PASSWORD `
  --secure-environment-variables GOOGLE_API_KEY="<your-gemini-api-key>" `
  --azure-file-volume-account-name $STORAGE `
  --azure-file-volume-account-key $STORAGE_KEY `
  --azure-file-volume-share-name $SHARE `
  --azure-file-volume-mount-path /app/data_and_output `
  --os-type Linux `
  --cpu 1 --memory 1.5 `
  --restart-policy Never
```

> Note: ACI only supports **one** Azure File Share mount per container in the
> simple CLI form. The easiest fix is to mount the share at a single path
> (e.g. `/app/data_and_output`) containing both a `data/` and `output/`
> subfolder, and point `main.py` at them with `--data` / `--output` args:
> ```
> ENTRYPOINT ["python", "main.py", "--data", "/app/data_and_output/data", "--output", "/app/data_and_output/output"]
> ```
> Update the Dockerfile's `ENTRYPOINT` line accordingly before building, or
> pass `--command-line` overrides in `az container create`.

## Step 5 — Watch it run (this replaces watching your terminal)

```powershell
az container logs --resource-group $RG --name $CONTAINER --follow
```

You'll see the exact same structured log lines you see locally (STEP 1/6,
STEP 2/6, "Calling LLM [extraction] …", etc.) streamed from the cloud.

## Step 6 — Get your results back

```powershell
az storage file download --account-name $STORAGE --account-key $STORAGE_KEY `
    --share-name $SHARE --path "output/final_report.csv" --dest ".\final_report.csv"
```

Or browse/download everything via **Azure Storage Explorer** (a free GUI
app) — much easier than the CLI for browsing many files:
https://azure.microsoft.com/features/storage-explorer/

## Step 7 — Run again later / clean up

Each `az container create` with the same name fails if the container already
exists (it already ran to completion). To re-run:

```powershell
az container delete --resource-group $RG --name $CONTAINER --yes
# then repeat the `az container create` command from Step 4
```

To tear down everything and stop being billed:

```powershell
az group delete --name $RG --yes --no-wait
```

---

## Why not a "normal" web deployment (App Service, etc.)?

App Service / Azure Functions HTTP triggers are for things that **respond to
requests** (e.g. a REST API or website). Your app has no such interface today
— it's a **run-to-completion batch job**. Container Instances is the direct
cloud equivalent of "run this script on a machine and shut it down when
done," which matches your current architecture with minimal code changes.

If later you want automatic runs on a schedule, or a simple upload button
for non-technical users, see the two natural next steps documented in
`README.md` under "Future Considerations" — moving to **Container Apps Jobs**
(scheduled/triggered execution) and/or a lightweight **Blob Storage trigger**
so files are picked up automatically instead of manual upload.

---
---

# Option B — Deploying a shareable web app with a public URL (Azure Container Apps)

Everything above deploys the **batch CLI** (`main.py`) — it runs once and
stops, with no browser URL. If you need to hand someone (e.g. a project
evaluator) a **link they can open in a browser**, upload files themselves,
and see results interactively, use this path instead. It deploys
[`streamlit_app.py`](../streamlit_app.py) — a thin Streamlit web UI wrapped
around the exact same `run_pipeline()` used by the CLI — as an **Azure
Container App** with public ingress.

This was validated end-to-end and is currently live at:

```
https://complaint-web-app.thankfulfield-30cb9743.eastus.azurecontainerapps.io
```

## What's different from Option A

| | Option A: Container Instance | Option B: Container App |
|---|---|---|
| Image | `Dockerfile` (runs `main.py`, exits) | `Dockerfile.web` (runs Streamlit, stays up) |
| Trigger | Manual `az container create` per run | Always listening for HTTP requests |
| Files in/out | Azure File Share, uploaded/downloaded via CLI | Uploaded through the browser UI directly |
| Result | You watch logs / download files via CLI | Evaluator uploads files and sees results live in browser |
| Public URL? | No | **Yes** — this is the point of this option |

## Prerequisites

Same as Option A (Azure CLI + Docker Desktop), plus these one-time resource
provider registrations if you haven't done them yet (Azure free-trial
subscriptions often start unregistered for these — this produced
`...not registered to use namespace...` errors during initial testing):

```bash
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.Storage
az provider register --namespace Microsoft.ContainerInstance
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights

# each takes ~1-2 minutes; check status with:
az provider show -n Microsoft.App --query registrationState -o tsv
# wait until it prints: Registered
```

Also install the (currently preview) Container Apps CLI extension once:

```bash
az extension add --name containerapp --upgrade
```

## Step 1 — Build and push the web image

From the project root (where `Dockerfile.web` lives):

```powershell
docker build -f Dockerfile.web -t complaint-web:local .

# Reuse the same ACR from Option A (or create one — see Option A Step 2)
docker login <ACR_NAME>.azurecr.io -u <ACR_NAME> -p <ACR_PASSWORD>
docker tag complaint-web:local <ACR_NAME>.azurecr.io/complaint-web:latest
docker push <ACR_NAME>.azurecr.io/complaint-web:latest
```

> Get `<ACR_PASSWORD>` with:
> `az acr credential show --name <ACR_NAME> --query "passwords[0].value" -o tsv`
> (run in Cloud Shell — needs `admin-enabled` on the registry, see Option A
> Step 4 equivalent: `az acr update --name <ACR_NAME> --admin-enabled true`)

## Step 2 — Create a Container Apps Environment (one-time)

A Container Apps Environment is the shared hosting boundary your app(s) run
inside — think of it as a mini virtual network + logging setup.

```bash
az containerapp env create \
  --name complaint-web-env \
  --resource-group $RG \
  --location $LOCATION
```

## Step 3 — Deploy the app with public ingress

```bash
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)

az containerapp create \
  --name complaint-web-app \
  --resource-group $RG \
  --environment complaint-web-env \
  --image $ACR_NAME.azurecr.io/complaint-web:latest \
  --registry-server $ACR_NAME.azurecr.io \
  --registry-username $ACR_NAME \
  --registry-password $ACR_PASSWORD \
  --target-port 8501 \
  --ingress external \
  --secrets google-api-key=<YOUR_GEMINI_API_KEY> \
  --env-vars GOOGLE_API_KEY=secretref:google-api-key \
  --cpu 1.0 --memory 2.0Gi
```

Key points:
- `--ingress external` is what makes it publicly reachable with a URL — this
  is the setting Option A (Container Instances) doesn't have an equivalent
  for.
- `--target-port 8501` matches the port Streamlit listens on inside the
  container (see `Dockerfile.web`'s `EXPOSE 8501`).
- `--secrets` + `--env-vars ...=secretref:...` is how the Gemini API key gets
  into the running container **without ever being visible to anyone using
  the app** — it's injected as an environment variable at the platform
  level, the same way `.env` works locally, just managed by Azure instead of
  a local file. Evaluators using the public URL never see or need this key.

## Step 4 — Get the public URL

```bash
az containerapp show --name complaint-web-app --resource-group $RG \
  --query properties.configuration.ingress.fqdn -o tsv
```

This prints something like:
`complaint-web-app.thankfulfield-30cb9743.eastus.azurecontainerapps.io`

Prefix it with `https://` and share that link. Anyone who opens it can
upload complaint documents and get structured data, a customer email, a
management summary, and a downloadable CSV — no account, no API key, no CLI
needed on their end.

## Step 5 — Updating the app after a code change

```powershell
docker build -f Dockerfile.web -t complaint-web:local .
docker tag complaint-web:local <ACR_NAME>.azurecr.io/complaint-web:latest
docker push <ACR_NAME>.azurecr.io/complaint-web:latest
```
```bash
az containerapp update --name complaint-web-app --resource-group $RG \
  --image <ACR_NAME>.azurecr.io/complaint-web:latest
```

## Step 6 — Stopping billing when you're done demoing

Container Apps bills for the app while it's provisioned (even mostly idle),
unlike Option A's Container Instance, which only bills while actively
running a batch job. Delete it when not needed:

```bash
az containerapp delete --name complaint-web-app --resource-group $RG --yes
```

Recreate later with the same `az containerapp create` command (Step 3) —
the image stays in ACR, so this is fast.

To remove everything from both options in one shot:

```bash
az group delete --name $RG --yes --no-wait
```

## Security note

Because the Gemini API key was typed directly into an `az containerapp
create` command (Cloud Shell has no simpler interactive secret-entry flow),
treat that key as exposed to your own shell history. Consider rotating it
in Google AI Studio (https://aistudio.google.com/app/apikey) after your
evaluation period, and updating the container app's secret with:

```bash
az containerapp secret set --name complaint-web-app --resource-group $RG \
  --secrets google-api-key=<NEW_KEY>
```
