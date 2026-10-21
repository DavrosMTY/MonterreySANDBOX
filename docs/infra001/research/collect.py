"""Read an official public price API; never provision or execute remote content."""
import datetime
import hashlib
import json
from pathlib import Path
import urllib.request

URL = ('https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/'
       'AWSDataTransfer/current/us-east-1/index.json')


def main():
    record = {'id': 'aws_data_transfer_catalog', 'requested_url': URL,
              'retrieved_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        request = urllib.request.Request(URL, headers={'User-Agent': 'MonterreyOpenWorld-public-research'})
        with urllib.request.urlopen(request, timeout=35) as response:
            body = response.read(12_000_001)
            record.update(http_status=response.status, final_url=response.url)
        if len(body) > 12_000_000:
            raise ValueError('Response exceeds research size cap')
        record.update(response_bytes=len(body), response_sha256=hashlib.sha256(body).hexdigest())
        data = json.loads(body)
        selected = []
        for sku, product in data.get('products', {}).items():
            attributes = product.get('attributes', {})
            if (attributes.get('fromLocation') == 'US East (N. Virginia)'
                    and attributes.get('toLocation') == 'External'
                    and attributes.get('transferType') == 'AWS Outbound'
                    and attributes.get('usagetype') == 'DataTransfer-Out-Bytes'):
                selected.append({'sku': sku, 'attributes': attributes,
                                 'prices': data.get('terms', {}).get('OnDemand', {}).get(sku, {})})
        if not selected:
            raise ValueError('Expected ordinary Internet outbound price not found')
        record['data'] = selected
    except Exception as exc:
        record['error'] = str(exc)
    result = {'collected_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'method': 'Unauthenticated official public URL, read-only, no provisioning',
              'records': [record]}
    Path(__file__).with_name('transfer.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: record.get(key) for key in ('id', 'http_status', 'error', 'response_bytes')}))


if __name__ == '__main__':
    main()
