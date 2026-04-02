# Scan Parameter Assembly

Use this reference after scan-target intent recognition and before `scan start`.

The model is responsible for deciding the scan case and assembling the final scan payload.
The Python helper remains the execution backend only.

## Goal

Turn a user scan request into one of two outcomes:

1. ask for clarification before scanning
2. produce the final Goby scan payload and start the scan with:

```bash
python scripts/goby_tool.py scan start --json-file payload.json
```

or:

```bash
python scripts/goby_tool.py scan start --json-body "<json>"
```

## Case handling

### 1. `host-only`

Definition:
- targets contain only IPs, CIDRs, or hostnames
- there is no separately specified port list

Action:
- do not start a scan yet
- ask the user to choose a port scope

Port-scope choices:
- enterprise
- compact
- full

Default port values:
- enterprise: `21,22,23,25,53,U:53,U:69,80,81,U:88,110,111,U:111,123,U:123,135,U:137,139,U:161,U:177,389,U:427,443,445,465,500,515,U:520,U:523,548,623,U:626,636,873,902,1080,1099,1433,U:1434,1521,U:1604,U:1645,U:1701,1883,U:1900,2049,2181,2375,2379,U:2425,3128,3306,3389,4730,U:5060,5222,U:5351,U:5353,5432,5555,5601,5672,U:5683,5900,5938,5984,6000,6379,7001,7077,8080,8081,8443,8545,8686,9000,9001,9042,9092,9200,9418,9999,11211,U:11211,27017,U:33848,37777,50000,50070,61616`
- compact: `21,22,80,U:137,U:161,443,445,U:1900,3306,3389,U:5353,8080`
- full: all ports

### 2. `host-with-ports`

Definition:
- targets contain IPs, CIDRs, or hostnames
- ports are explicitly provided

Action:
- assemble a normal host-and-port scan payload
- do not include `options.hostListMode`

### 3. `url-only`

Definition:
- targets contain one or more `http://` or `https://` URLs
- there is no separately specified port list

Action:
- assemble a URL host-list scan payload
- include `options.hostListMode=true`
- do not separately inject port values just because a URL embeds `:3001`

### 4. `url-with-ports`

Definition:
- targets contain one or more `http://` or `https://` URLs
- ports are explicitly provided outside the URLs

Action:
- assemble a normal scan payload
- do not include `options.hostListMode`
- explicit ports win over the URL-only interpretation

## Mixed-target rule

If a request mixes URLs and host-only targets:
- without separately specified ports: ask a clarifying question
- with separately specified ports: assemble a normal host-and-port scan payload

## Minimal payload rule

Only include keys that are actually needed.

Do not include keys when the value is:
- `null`
- `""`
- `{}`
- `[]`

If a section becomes empty after pruning, omit the whole section.

## Required payload shape

At minimum, scan payloads should use:

```json
{
  "asset": {
    "ips": []
  }
}
```

Optionally include:

```json
{
  "asset": {
    "ips": [],
    "ports": ""
  },
  "options": {
    "hostListMode": true
  }
}
```

Use the smallest valid form that matches the request.

## Payload assembly rules

### For `host-with-ports`

Use:

```json
{
  "asset": {
    "ips": ["192.0.2.1", "192.0.2.2"],
    "ports": "80,443"
  }
}
```

### For `url-only`

Use:

```json
{
  "asset": {
    "ips": [
      "http://198.51.100.1:3001",
      "https://198.51.100.2"
    ]
  },
  "options": {
    "hostListMode": true
  }
}
```

### For `url-with-ports`

Use:

```json
{
  "asset": {
    "ips": [
      "http://198.51.100.1:3001",
      "https://198.51.100.2"
    ],
    "ports": "80,443"
  }
}
```

## Conversation behavior

Before scanning, the assistant should internally decide:
- case: `host-only`, `host-with-ports`, `url-only`, or `url-with-ports`
- whether clarification is needed
- the final payload if no clarification is needed

If clarification is needed, ask only for the missing decision.

Examples:
- `scan 192.0.2.1` -> ask for `enterprise`, `compact`, or `full`
- `scan 192.0.2.1 port 80` -> build payload and continue
- `scan http://192.0.2.1:3001 https://192.0.2.2` -> build `hostListMode=true` payload and continue
- `scan http://192.0.2.1:3001 https://192.0.2.2 with ports 80,443` -> build normal payload and continue

## Execution reminder

After payload assembly:
1. run `preflight --persist`
2. run `env get`
3. if clarification is not required, run `scan start`

Do not modify the helper script just to express these four cases.
