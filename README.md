# updateDNS

### Problem
Sending emails from an appliance to users in Office 365.

### Challenge
Don't want to create an account for the appliance so it can send through O365s servers authenticated.

### Solution
Send directly to O365 SMTP servers, with IP added to SPF.

### Challenge 2
IP is dynamic, and may change and thus break SPF and email delivery.

### Solution 2
This silly little app. It is invoked through an HTTP GET from the appliance, and checks if the IP has changed, and updates the DNS record through the DNSimple API if it has.

### Details
The app updates an A record, so that must be included in the SPF record. E.g. like so:
```
v=spf1 a -all
```
And the config.json file must be updated with the DNS details and a token.

The app must be placed behind a reverse proxy that does some sort of authentication (e.g. Caddy with the JWT plugin) and inserts the client IP in the X-Forwarded-For header. Then it can be invoked from the applicance via a cron job:

```bash
0 5 * * * curl https://api.example.com/updateDNS -H 'Authorization: Bearer <token>'
```

This will check that the DNS record matches, and potentially update it if it don't, every day at 5:00.
