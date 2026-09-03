"""Local H3 server; use AVVIA.bat for automatic setup and background launch."""
import argparse
import uvicorn
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8775);a=p.parse_args()
    uvicorn.run('app.server:app',host='127.0.0.1',port=a.port,log_level='info')
