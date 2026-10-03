# Suffix inference

How do I let the file name choose the decoding?

[example.py](example.py) — run from the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/suffix_inference/example.py
```

Expected output:

```text
sales.csv.gz -> sales.csv; .gpg requires key material
```

Suffixes are parsed right to left and parsing stops at the first unknown
suffix: `.gz`/`.gzip` map to `Gzip`, `.gpg`/`.asc`/`.pgp` to `GPG`. Inference is
opt-in (`infer=True`) and read-only; writes always take an explicit `pipeline=`.
`infer=True` together with `pipeline=` is a `ValueError`. A single transform may
be passed without wrapping it in `Pipeline`.

Next: [streaming](../streaming/).
