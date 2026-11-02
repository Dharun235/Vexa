# Your first Vexa program

For Vexa 0.1.0. [Documentation home](README.md) · [Language reference](language-reference.md)

Vexa is a small language for detecting and counting objects in still images. You write Vexa commands; the Vexa interpreter runs them in order and uses a pretrained YOLO model through ONNX Runtime on your CPU. You do not need to write Python, train a model, or have a GPU.

## Where do I write and run it?

| Task | Place |
| --- | --- |
| Start the Vexa application | Your computer's terminal, inside the Vexa project folder |
| Write Vexa commands and view results | The local browser playground at http://127.0.0.1:8000 |
| Save a program for later | A plain text file ending in `.vexa`, using any text editor |
| Execute a saved file from a terminal | Send the file and an image to the running local API, as shown below |

Vexa currently has no standalone `vexa program.vexa` command, interactive REPL, compiler, or VS Code extension. Python runs the interpreter behind the playground; `.vexa` files are not Python scripts or C++ source files. The browser editor is named `main.vexa`, but it does not automatically save that text to disk.

## 1. Start Vexa

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node.js 20.19+ or 22.12+. The commands below use a macOS/Linux shell; the startup scripts have been verified on macOS. Windows users can use a compatible WSL environment, but native Windows startup has not been verified.

If you already have this project, open a terminal in its folder and run:

```sh
./scripts/dev.sh
```

For the existing checkout on this machine, that means:

```sh
cd /Users/dharunkumar/Dev/Vexa
./scripts/dev.sh
```

For a fresh checkout of the prototype branch:

```sh
git clone --branch codex/local-mvp https://github.com/Dharun235/Vexa.git
cd Vexa
./scripts/dev.sh
```

The first startup installs a Python 3.12 environment with uv, converts the small YOLO model to ONNX, and builds the React playground. Conversion temporarily needs PyTorch; the script removes the conversion dependencies from the normal environment afterwards. This first setup requires internet access and more disk space than everyday use.

Later starts reuse the model and frontend build. Inference runs locally on CPU with two threads. No external inference account or key is needed. Keep the terminal open while using the playground. Press **Ctrl+C** there to stop the server.

Open **http://127.0.0.1:8000** in your browser. If port 8000 is already serving Vexa, use that running instance rather than starting a second one.

## 2. Upload a photo

Click the image area and select `examples/street.jpg`, or drag a photo onto it. The other included photos are `examples/football.jpg` and `examples/dog-bicycle.jpg`.

Use a JPEG, PNG, or WebP image up to 10 MB and 20 megapixels. Uploads are processed in memory. The application does not save them to disk or send them to a remote inference service.

## 3. Write five lines

Paste this into the playground editor:

```vexa
load "street.jpg"
detect person
count person
draw boxes
show image
```

Read it as:

1. Use my uploaded photo, calling it `street.jpg` inside this program.
2. Find people.
3. Count the people found.
4. Draw boxes around those detections.
5. Display the resulting image.

The name in `load` is an alias. It does not have to match the uploaded file and never opens a path on your computer. Every `load` in a run refers to the same uploaded photo.

## 4. Run and read the result

Click **Run program**. The image output shows the boxes, the count appears below it, and **Execution log** explains each step. The included street photo produced four person detections during prototype verification; predictions can vary with model changes.

Use **Download image** to save the processed PNG. A missing `show image` still allows logs and counts, but produces no image output. Counts are predictions, so check the boxes when accuracy matters to your task.

## 5. Try a second program

Use the dog/bicycle photo and detect everything the model recognises:

```vexa
load "dog-bicycle.jpg"
detect all
count dog
count bicycle
count all
print "Finished looking."
draw boxes
show image
```

`detect all` makes several labels available to count without running inference repeatedly. Counting does not rerun the detector. Each click of Run starts a fresh execution; it does not retain state from the previous run.

## Save and run a `.vexa` file

Copy your code into a plain text file such as `my-program.vexa`. To use it in the playground later, open that file in a text editor and paste its contents into Vexa. The current UI uploads images, not source files.

To execute the included saved program from a second terminal while Vexa is running, start in the project folder:

```sh
curl --fail-with-body http://127.0.0.1:8000/execute \
  --form 'source=<examples/demo.vexa' \
  --form 'image=@examples/street.jpg' \
  --output /private/tmp/vexa-result.json
```

`source=<...` sends the file contents as the source field. `image=@...` uploads the image file. The response is JSON with logs, counts, detections, and a PNG data URL. To inspect the counts and save the image:

```sh
.venv/bin/python - <<'PY'
import base64
import json
from pathlib import Path

result = json.loads(Path('/private/tmp/vexa-result.json').read_text())
print(result['counts'])
if result['image']:
    encoded = result['image'].split(',', 1)[1]
    Path('/private/tmp/vexa-result.png').write_bytes(base64.b64decode(encoded))
    print('Saved /private/tmp/vexa-result.png')
PY
```

These temporary output paths are for the verified macOS workflow; choose appropriate paths on another system. The server also exposes interactive API documentation at **http://127.0.0.1:8000/docs** and health status at **http://127.0.0.1:8000/api/health**.

## Fix a common problem

| What you see | What to do |
| --- | --- |
| Cannot reach Vexa / connection refused | Start `./scripts/dev.sh` and keep its terminal open. Check the address and port. |
| Address already in use | Use the existing Vexa instance, or stop the process you previously started on port 8000. |
| Add an image | Upload a photo before clicking Run. |
| Load your image first | Put `load "image.jpg"` before image commands. |
| Run detect before counting or drawing | Put a `detect` command before `count`, `print person`, or `draw boxes`. |
| Unknown object | Use an exact [supported label](language-reference.md#supported-object-labels), such as `person`, or use `all`. |
| Invalid command | Check spelling, double quotes, and one command per line. Do not add semicolons. |
| No image output | Put `show image` after `draw boxes`. |
| Zero objects | Try `detect all` and inspect the photo. The model may not recognise the requested object. |
| Model is missing | Run `./scripts/setup-model.sh` once with internet access, then restart the server. |
| Changes to frontend source are missing | Run `cd frontend && npm run build`, then restart the server and reload the page; or follow the development workflow in [CONTRIBUTING.md](../CONTRIBUTING.md). |

Next: keep the [six-command reference](language-reference.md#command-reference) nearby as you experiment.
