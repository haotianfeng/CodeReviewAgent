def load_value(loader):
    try:
        return loader()
    except:
        return None
