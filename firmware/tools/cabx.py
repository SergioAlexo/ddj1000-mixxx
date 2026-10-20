import struct,zlib,sys,os
d=open(sys.argv[1],'rb').read(); off=d.find(b'MSCF\0\0\0\0'); c=d[off:]; out=sys.argv[2]
sig,_,cbCab,_,coffFiles,_,vmin,vmaj,nFolders,nFiles,flags,setID,iCab=struct.unpack_from('<4sIIIIIBBHHHHH',c,0)
print('cab at',hex(off),'size',cbCab,'folders',nFolders,'files',nFiles,'flags',flags)
p=36; folders=[]
for i in range(nFolders):
    coff,ndata,typ=struct.unpack_from('<IHH',c,p); p+=8; folders.append((coff,ndata,typ))
# decompress folders
fdata=[]
for coff,ndata,typ in folders:
    q=coff; buf=b''; zd=None; dictb=b''
    for b in range(ndata):
        csum,cb,ucb=struct.unpack_from('<IHH',c,q); blk=c[q+8:q+8+cb]; q+=8+cb
        if typ&0xf==1:
            assert blk[:2]==b'CK'
            z=zlib.decompressobj(-15,zdict=dictb) if dictb else zlib.decompressobj(-15)
            u=z.decompress(blk[2:])+z.flush()
            dictb=(dictb+u)[-32768:]
        else: u=blk
        assert len(u)==ucb,(len(u),ucb); buf+=u
    fdata.append(buf); print('folder type',typ,'blocks',ndata,'bytes',len(buf))
p=coffFiles
for i in range(nFiles):
    cbFile,uoff,ifold,date,time,attr=struct.unpack_from('<IIHHHH',c,p); p+=16
    e=c.index(b'\0',p); name=c[p:e].decode(); p=e+1
    fn=os.path.join(out,name.lstrip('\\'))
    open(fn,'wb').write(fdata[ifold][uoff:uoff+cbFile])
    y=(date>>9)+1980;mo=(date>>5)&15;dd=date&31;h=time>>11;mi=(time>>5)&63
    print(f'{name:20s} {cbFile:8d}  {y}-{mo:02}-{dd:02} {h:02}:{mi:02}')
