# DCL Buf Plugin

A custom [buf](https://buf.build/) lint plugin that enforces DCL-specific proto
schema requirements.

## Rules

| Rule ID                       | Description                                                                    |
| ----------------------------- | ------------------------------------------------------------------------------ |
| `DEFCL_EDITION`               | Files must use edition 2023                                                    |
| `DEFCL_NO_BOOL`               | Fields cannot use the `bool` type                                              |
| `DEFCL_NO_BYTES`              | Fields cannot use the `bytes` type                                             |
| `DEFCL_NO_ANY`                | Fields cannot use `google.protobuf.Any`                                        |
| `DEFCL_ENUM_IN_MESSAGE`       | Enums must be defined inside messages                                          |
| `DEFCL_ENUM_ZERO_UNSPECIFIED` | Enum zero values must be named exactly `UNSPECIFIED`                           |
| `DEFCL_FIELD_NAME_UNDERSCORE` | Underscores in field names must be followed by letters; no trailing underscore |
| `DEFCL_TIME_FIELD_SUFFIX`     | Time-related fields must have appropriate suffixes                             |

## Building

```bash
go build -o buf-plugin-defcl .
```

## Testing

```bash
go test -v ./...
```

## Usage

Configure the plugin in your `buf.yaml`:

```yaml
lint:
  use:
    - STANDARD
  plugins:
    - path: ./buf/buf-plugin-defcl
```
