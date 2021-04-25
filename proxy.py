import sys
import blocklist
import server


def main(args):
    args.pop(0) # name of application

    arg = args.pop(0)
    if arg == "blocklist":
        arg = args.pop(0)
        if arg == "add":
            blocklist.add_to_blocklist(args)
        elif arg == "remove":
            blocklist.remove_from_blocklist(args)
        else:
            print(f"Unrecognised qualifier for 'blocklist' command: '{arg}'")
            print("Usage: blocklist add|remove <urls>")
            exit(1)
    elif arg == "start":
        print_welcome()
        server.start_proxy(args)
    elif arg == "-h" or arg == "help":
        print_help()
        exit(1)
    else:
        print(f"Unrecognised command '{arg}'")
        exit(1)


def print_welcome():
    welcome_message = '''
       ______________________________________________________________
     .'  __________________________________________________________  '.
     : .'                                                          '. :
     | |      ________________________________________________      | |
     | |    .:________________________________________________:.    | |
     | |    |                                                  |    | |
     | |    |   Welcome to PyProxy.                            |    | |
     | |    |                                                  |    | |
     | |    |                                                  |    | |
     | |    |   Press ^C (CTRL + C) to stop.                   |    | |
     | |    |                                                  |    | |
     | |    |                                                  |    | |
     | |    |                                                  |    | |
     | |    |                                                  |    | |
     | |    |                                                  |    | |
     | |    |                                                  |    | |
     | |    |            __________________________            |    | |
     | |    |           |  |  |  |  |  |  |  |  |  |           |    | |
     | |    '.__________|__|__|__|__|__|__|__|__|__|__________.'    | |
     | |                                                            | |
     | |                            iMac                            | |
     : '.__________________________________________________________.' :
      ".____________________________\__/____________________________."
                                     ||
                                     ||
                                     ||
                                  ___||___
                            _.--""   ""   ""--._
                         .'"       .-L-.        "'.
                       .'          : _ (           '.
                     .'             " "              '.
                    .'                                '.
                    :         ________________         :
                   .'       .'                '.       '.
                   :        '.________________.'        :
                   |----......______    ______......----|
                   :                """"                :
                   '.                                  .'
                     "-.____. . . . . . . . . . ____.-"
                            """"""--------""""""
    '''
    print(welcome_message)


def print_help():
    print("Usage: start [-v] [-t]")
    print("Options:")
    print("\t -v\t\t\t Enable verbose logging to show cache requests.")
    print("\t -t\t\t\t Enable timing information.")

    print("\n\nUsage: blocklist add|remove <urls>")
    print("Options:")
    print("\t add\t\t\t Adds a URL or group of URLs to a blocklist. When the user attempts to visit these URLs the connection will be refused.")
    print("\t remove\t\t\t Removes a URL or group of URLs from the blocklist, if it exists.")


if __name__ == "__main__":
    main(sys.argv)
