# Mockery setup

The config and Makefile target that generate mocks, and the v2 to v3 migration note. The rules for using mocks live in [`../SKILL.md`](../SKILL.md).

Mocks are declared in `.mockery.yaml` at the module root and regenerated with
`make generate-mocks`. The generated files are committed to the repo.

Use **mockery v3** with the `testify` template (v2 is pinned to an old
`golang.org/x/tools` and cannot parse modules that declare `go 1.25`+). v3
generates the typed `EXPECT()` API by default — there is no `with-expecter` flag.

```yaml
# .mockery.yaml (v3)
template: testify
dir: "{% raw %}{{.InterfaceDir}}{% endraw %}/mocks"   # a mocks/ subpackage next to each interface
structname: "Mock{% raw %}{{.InterfaceName}}{% endraw %}"
pkgname: mocks
filename: "{% raw %}{{.InterfaceName | snakecase}}{% endraw %}.go"
template-data:
  unroll-variadic: true
packages:
  {{ template.go_module | default("github.com/yourorg/project/api") }}/internal/core/services:
    interfaces:
      ProfileRepository: {}
      ProfileUserLookup: {}
  {{ template.go_module | default("github.com/yourorg/project/api") }}/internal/core/ports:
    interfaces:
      ProfileService: {}
```

```makefile
# Makefile — wrapped in timeout per the command-timeout convention
generate-mocks:
	timeout 120 go run github.com/vektra/mockery/v3@v3.7.0
```

> Upgrading an existing v2 config? Run `mockery migrate` (v3) — it rewrites the
> v2 keys (`mockname`→`structname`, `outpkg`→`pkgname`, drops `with-expecter`).
