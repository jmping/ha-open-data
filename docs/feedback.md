# Demand-driven portal feedback

The first HACS release keeps feedback optional and metadata-only. Home Assistant does not upload dataset records, credentials, account data, IP addresses, or location history.

Each installation creates one random UUID in Home Assistant storage. A central collector must treat `(installation_id, portal_id)` as one installation vote regardless of how many times the integration runs.

Before a report is sent, the integration hashes normalized portal metadata. An unchanged portal produces the same hash and is suppressed locally after a successful submission. A new report is created only when the discovered metadata changes.

Suggested payload fields are:

- platform and platform confidence;
- public portal URL;
- public dataset identifiers and titles;
- matched and unmatched canonical dataset types;
- crawler capability or mapping errors.

Submission must remain opt-in. The central service should aggregate unique installations and unique issue reporters before writing queue inputs. Raw repeated requests must never be used as priority signals.
