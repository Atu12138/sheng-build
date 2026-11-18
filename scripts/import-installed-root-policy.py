"""Import authenticated public policies for the root disk already installed on this tablet."""
from pathlib import Path
import base64,hashlib,json,sys
record=json.loads(Path(sys.argv[1]).read_text())
policies=Path(sys.argv[2])
assert record['schema']==1
key=base64.b64decode(record['public_key_base64'],validate=True)
digest=hashlib.sha256(key).hexdigest()
assert len(key)==395 and key[:8]==b'VROOTKEY' and digest==record['public_key_sha256']
assert digest=='a9ee2ee5b2020b2f2e5a3b7e79fdd369d151661b1929bd3f610987bd32619aee'
outputs=[]
for name in ('OS','SystemOS','App'):
 destination=policies/name
 selected=json.loads((destination/'verification.json').read_text())
 header=base64.b64decode(record['signed_headers'][name],validate=True)
 assert len(header)==544 and header[56:88].hex()==selected['image_sha256']
 assert header[120:152].hex()==digest
 encoded=bytes.fromhex('3031300d060960864801650304020105000420')+hashlib.sha256(header[:160]).digest()
 expected=b'\0\1'+b'\xff'*(384-len(encoded)-3)+b'\0'+encoded
 signature=pow(int.from_bytes(header[160:],'big'),int.from_bytes(key[392:],'big'),int.from_bytes(key[8:392],'big')).to_bytes(384,'big')
 assert signature==expected, name+': installed root signature verification failed'
 selected['trusted_key_sha256']=digest
 outputs.append((destination,header,selected))
for destination,header,selected in outputs:
 (destination/'manifest.header.bin').write_bytes(header)
 (destination/'trusted-key.bin').write_bytes(key)
 (destination/'verification.json').write_text(json.dumps(selected,indent=2)+'\n')
print('Authenticated and imported current installed root public key and three signed headers.')
