# DmD
The Donate My Data (DmD) project allows people to volunteer to donate their medical data residing in VistA for use by developers or other projects.  It obfuscates key identifiers to keep the real identity of the record holders data private.

The DmD system is broken into four parts. LEAF Frontend, DmD Engine, DmD Acquirer, and DmD Scrubber.

LEAF frontend - Veteran Employees sign up to donate data in this system. DmD Engine - Maintains a listing of current donators mapped to VistA DmD Acquirer - Acquires the donated data from VistA systems DmD Scrubber - Scrubs identifable information from the records in DmD

A more detailed description of these processes follow:
LEAF Frontend

The LEAF frontend is the web-based graphical user interface that VA Employee's who are Veterans can sign-up to be included in the DonateMyData (DmD) program.
DmD Engine

The DmD Engine is a back-end process that interrogates the LEAF database against the DmD Logic database to discover which employees are currently in the DmD system. It automatically removes Employees who have chosen to no longer donate their data as well as adds new data donators to the program.
DmD Acquirer

The DmD Acquirer is a process that performs the following functions:

    Performs MVI look ups to positiviely identify participants in the DmD program.
    Performs VPR RPC calls to VistA to acquire patient records in the XML output format.
    Performs VPR RPC calls to VistA to acquire new patient data such as progress notes, lab results, consults, appointment details such as new appointments, no shows, etc...

*Data will be acquired to the DmD Alpha database which contains the raw unaltered records. Currently this is a directory called acquirer with sub folders one (1) per data donator.
DmD Scrubber

The DmD Scrubber is a processor that interates through the DmD Alpha records and de-identifies them. It uses a library of common names, places, diagnosis, and regular expression powered queries to find addresses and other common linguistically identifable strings and replaces them randomly with synthetic data. It is based upon the deid-1.1 codebase written in Perl but greatly enhanced for the needs of DmD.
