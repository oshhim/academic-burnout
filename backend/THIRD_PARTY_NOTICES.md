# Third-party data and software

## Component 3 synthetic fixtures

Component 3's generator, supplied risk-model artifact and simulation evaluation use generated numerical observations only. No public dataset is presented as a burnout-labelled student dataset, and no human participants are represented by these fixtures. The bundled original RAVDESS audio/derived C2 artifacts retain the separate terms below. All installed software dependencies retain their own licenses.

## Original public sample audio

Three unchanged RAVDESS speech WAVs by Steven R. Livingstone and Frank A. Russo are included in `app/static/voice_samples/`. They are actor 19's normal-intensity neutral, happy and angry recordings for the first statement/repetition. Exact filenames and SHA-256 hashes are in `manifest.json`.

Source: <https://zenodo.org/records/1188976>

License: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0): <https://creativecommons.org/licenses/by-nc-sa/4.0/>

Attribution: Livingstone SR, Russo FA (2018). The Ryerson Audio-Visual Database of Emotional Speech and Song (RAVDESS): A dynamic, multimodal set of facial and vocal expressions in North American English. PLoS ONE 13(5): e0196391. <https://doi.org/10.1371/journal.pone.0196391>

No modifications were made to the included original WAVs. Their small demonstration is not a new independent evaluation. The training model and RAVDESS-derived evaluation/features in `models/voice` are provided for this noncommercial academic prototype under CC BY-NC-SA 4.0 with the above attribution. The original RAVDESS dataset owner provides a separate commercial-licensing route.

## openSMILE

The Python dependency supplies the standard eGeMAPSv02 acoustic feature extractor. Its source/binaries are available for private, research and educational use under its research license; commercial-product use requires the appropriate separate license. No openSMILE source/binary is copied into this archive; pip installs the dependency and its terms.

Official package/documentation and license information: <https://audeering.github.io/opensmile-python/>

Citation: Eyben F, Wöllmer M, Schuller B (2010). openSMILE — The Munich Versatile and Fast Open-Source Audio Feature Extractor. ACM Multimedia.

## Other dependencies

FastAPI, SQLAlchemy, scikit-learn, NumPy, SciPy, SoundFile/libsndfile, joblib and other installed packages retain their respective licenses. Their wheels and Python environments are not redistributed in this archive. The optional Component 1 MediaPipe task asset is not included.

## Component 4 original catalog and simulation

The six optional activity instructions, fixed rule policies and synthetic preference/feedback simulator in this package are original implementation content. No third-party activity dataset or real participant records are included. Synthetic evaluation results are not empirical health outcomes. Component 2's public-audio licence and attribution remain applicable to its distributed recordings.
