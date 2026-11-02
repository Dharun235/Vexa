from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from vexa import __version__
from vexa.ast_nodes import VexaError
from vexa.interpreter import execute_commands
from vexa.validation import check_source
from vexa.vision import MAX_UPLOAD, Vision, decode_image

app = FastAPI(title="Vexa", version=__version__)
vision = Vision()


@app.get("/api/health")
def health():
    return {"status": "ok", "model_loaded": vision.model is not None}


def run_program(source, data):
    commands = check_source(source)
    return execute_commands(commands, decode_image(data), vision)


@app.post("/execute")
async def execute_program(source: Annotated[str, Form()], image: Annotated[UploadFile, File()]):
    try:
        data = await image.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise VexaError("Image exceeds the 10 MB upload limit.", kind="upload")
        return await run_in_threadpool(run_program, source, data)
    except VexaError as exc:
        return JSONResponse(status_code=400, content={"error": exc.as_dict()})
    finally:
        await image.close()


DIST = Path(__file__).with_name("web")
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="playground")
