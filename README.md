# mock-dir-content

Allows to take a snapshot of a folder, regenerate its structure without its real data.

IMPORTANT: symlinks are always create with their exact content from the source.

Expansion modes :

- `empty`: regular files are created empty (uses less space, can be cached by middlewares)
- `random`: regular files are created with random bytes (exact size, but prevents caching)
- `sparse`: regular files are created "with void" (exact size, can be cached by middlewares)

To check that a file is sparse, use `stat -c '%s %b' file_path` :

- the first value is "declared file size" in bytes,
- the second value is number of blocks actually allocated on disk

Look at [test.sh](test.sh) to see how to use this tool, and test with a small sample :

```shell
DEBUG_HEX=1 CLEAN_TARGET=1 ./test.sh
```

Of course, the main reason i created these script is :

- to be able to "optimize-mirror" file trees
- from any host to any host
- without copying any script or data files
- and be able to have different expansion modes

So in fact, my usual commands are something like this :

```shell
ssh "${SRC_HOST}" python3 -c "${CAPTURE}" "${SRC_DIR}" | \
ssh "${TGT_HOST}" python3 -c "${EXPAND}"  "${TGT_DIR}" "${MODE}"
```
