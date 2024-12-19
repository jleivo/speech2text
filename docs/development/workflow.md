
## Developing new feature

1. Write code to implement the new feature.
2. Do commits, once ready for testing
```bash
make test_build # creates with tag git short hash (git rev-parse --short HEAD)
make test_push # pushes to repo
```
3. pull in target
4. repeat

once ready with the work, create release X.Y.Z

```bash
make release # pushes Z one up
make minor_release # pushes Y one up
make major_release # pushes X one up
```