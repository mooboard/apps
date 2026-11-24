# Uptime

A status light for each service you count on, green when it's up and red when it's down.

Each service is a link your board checks every minute. A status page link (most services have one ending in /api/v2/status.json) shows issues and outages as the service reports them. Any other link that answers with JSON counts as up, and a link that doesn't answer counts as down.

GitHub, Cloudflare, and Discord come set up. Type none to leave a service out.

## Settings

- Service 1 to Service 4 are the links to check.
