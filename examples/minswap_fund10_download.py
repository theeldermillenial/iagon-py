from iagon import IagonAdapter

from pycardano import HDWallet

# Give the file id of the Minswap Catalyst Grouping data
file_id = "65296cf4eba1933b118b368f"

# Create a random seed phrase to access Iagon
# Why is this needed? To access Iagon, we need to get an auth token using CIP8, which
# requires a wallet signature. Since it's public data, it doesn't matter what wallet we
# use, so generate a random one.
seed_phrase = HDWallet.generate_mnemonic()

# Create the Iagon session
with IagonAdapter.session(seed_phrase) as session:
    # Open a file to write the binary data to
    with open("minswap_catalyst_groups.zip", "wb") as fw:
        fw.write(session.download(file_id=file_id))
