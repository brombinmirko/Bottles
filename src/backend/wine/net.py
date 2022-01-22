from typing import NewType

from bottles.utils import UtilsLogger # pyright: reportMissingImports=false
from bottles.backend.wine.wineprogram import WineProgram

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)


class Net(WineProgram):
    program = "WINE Services manager"
    command = "net"

    def start(self, name: str = None):
        args = "start"

        if name is not None:
            args = f"start '{name}'"
        
        return self.launch(args=args, comunicate=True)

    def stop(self, name: str = None):
        args = "stop"

        if name is not None:
            args = f"stop '{name}'"
        
        return self.launch(args=args, comunicate=True)

    def stop(self, name: str = None):
        # this command has no documentation, not tested yet
        args = "use"

        if name is not None:
            args = f"use '{name}'"
        
        return self.launch(args=args, comunicate=True)

    def list(self):
        services = []
        res = self.start()
        
        if len(res) == 0:
            return services
        
        res = res.strip().splitlines()
        i = 0

        for r in res:
            if i == 0:
                i += 1
                continue
            
            r = r[4:]
            services.append(r)
            i+=1
        
        return services
