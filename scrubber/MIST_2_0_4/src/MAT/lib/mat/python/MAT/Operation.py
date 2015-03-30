# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# It turns out that a number of places in MAT have the same need,
# namely for an operation object which allows us to
# export argument lists to things like command line tools
# and CGI scripts. The operations should support
# argument validation, and provide support for
# obligatory, optional and repeatable arguments.

# The idea is that there will be a group of arguments,
# some of which might be shared by multiple operations.
# If multiple operations have different interpretations,
# then we signal an error, but otherwise, Conflicts are
# checked globally (across all arguments) at parse
# time. So we have to check to see if the argument is
# already present.

import optparse, types

class OperationError(Exception):
    pass

# We piggyback off the existing options.  We only
# add an option if the argument isn't already present;
# if it is, we make sure it's compatible with the
# argument that's already present, and record
# it in the global element. Then, later, we
# retrieve the relevant keys and values by filtering
# on the name of the step.

# First step: everybody needs to be using my OptionParser, Option,
# and OptionGroup.

#
# Option
# 

def check_boolean(option, opt, value):
    if value == "yes":
        return True
    elif value == "no":
        return False
    else:
        raise optparse.OptionValueError("option %s: value '%s' is neither 'yes' or 'no'" % (opt, value))

def help_is_template(help):
    return (help is not None) and (help.find("%(prefix)s") > -1)

class Option(optparse.Option):

    # Add the Boolean type. But it's only available with a long opt,
    # because of how we implement the workaround.
    
    TYPES = ("boolean",) + optparse.Option.TYPES
    TYPE_CHECKER = optparse.Option.TYPE_CHECKER.copy()
    TYPE_CHECKER["boolean"] = check_boolean
    ALL_ATTRS = optparse.Option.ATTRS + ["side_effect_callback", "side_effect_callback_args",
                                         "side_effect_callback_kwargs"]

    def _peel(self, side_effect_callback = None,
              side_effect_callback_args = None, side_effect_callback_kwargs = None,
              **kw):
        self.side_effect_callback = side_effect_callback
        self.side_effect_callback_args = side_effect_callback_args
        self.side_effect_callback_kwargs = side_effect_callback_kwargs
        return kw

    def __init__(self, *opts, **kw):
        # Peel off the container_pair option, etc.
        kw = self._peel(**kw)
        optparse.Option.__init__(self, *opts, **kw)
        if self.type == "boolean":
            if self.default is optparse.NO_DEFAULT:
                self.default = False
            if self._short_opts:
                raise optparse.OptionError("boolean type not permitted with short opts: %s" % \
                                           ", ".join(self._short_opts), self)
        if (self.type == "choice") and (self.metavar is None) and (self.choices is not None):
            self.metavar = " | ".join(self.choices)

        # Default values.
        # THE NAME IS NOT THE DEST.
        self._matName = self.get_opt_string()[2:]
        # This is a container for options which can't be registered
        # because they're duplicates.
        self.phantom_container = None

    def process(self, opt, value, values, parser):
        if self.type == "boolean":
            if isinstance(self.container, OptionGroup):
                p = self.container.parser
            else:
                p = self.container
            if isinstance(p, OptionParser):
                # Better add a value.
                # The default is OPPOSITE of the occurrence.
                if self.default is False:
                    value = "yes"
                else:
                    value = "no"                 
        r = optparse.Option.process(self, opt, value, values, parser)
        # We have to keep track of the options we've SEEN,
        # because later, when we extract in the aggregator, it's
        # gonna want to know.
        self._after_process(value, values, parser)
        return r

    def _after_process(self, value, values, parser):
        if not hasattr(values, "_optionsSeen"):
            values._optionsSeen = set([])
        values._optionsSeen.add(self)

    def take_action(self, action, dest, opt, value, values, parser):
        # The value has been converted at this point.
        r = optparse.Option.take_action(self, action, dest, opt, value, values, parser)
        self._maybe_do_side_effect_callback(opt, value, parser)
        return r

    def _maybe_do_side_effect_callback(self, opt, value, parser):        
        if self.side_effect_callback:
            args = self.side_effect_callback_args or ()
            kwargs = self.side_effect_callback_kwargs or {}
            self.side_effect_callback(self, opt, value, parser, *args, **kwargs)
        
    def _copyForPrefix(self, prefix):
        # Let's mangle the prefix.
        optName = "--" + prefix + self.get_opt_string()[2:]        
        # We don't preserve the destination. Just infer it.
        opts = dict([(a, getattr(self, a, None)) for a in self.ALL_ATTRS if getattr(self, a, None) is not None])
        try:
            del opts["dest"]
        except KeyError:
            pass
        if help_is_template(opts.get("help")):
            opts["help"] = opts["help"] % {"prefix": prefix}
        return Option(optName, **opts)

    # The hash option parsers all want a guaranteed value.
    
    def _copyForBoolean(self):
        opts = dict([(a, getattr(self, a, None)) for a in self.ALL_ATTRS if getattr(self, a, None) is not None])
        # The default is the opposite of the expected value.
        if self.action == "store_true":
            opts.update({"action": "store", "type": "boolean", "default": False})
        elif self.action == "store_false":
            opts.update({"action": "store", "type": "boolean", "default": True})
        return Option(self.get_opt_string(), **opts)

    def copy(self):
        opts = dict([(a, getattr(self, a, None)) for a in self.ALL_ATTRS if getattr(self, a, None) is not None])
        return Option(self.get_opt_string(), **opts)        
          
    # When the parser is an option parser (see below), boolean
    # can't take an argument. See also process() above.

    def get_container(self):
        return (hasattr(self, "container") and self.container) or self.phantom_container

    def get_parser(self):
        c = self.get_container()
        if isinstance(c, OptionGroup):
            return c.parser
        else:
            return c
    
    def takes_value(self):
        if self.type == "boolean":
            p = self.get_parser()
            # It takes a value if it's not a commandline parser.
            return not isinstance(p, OptionParser)
        else:
            return optparse.Option.takes_value(self)

    # The option, at this point, will not have a container, I
    # don't think.
    
    def activate(self, parser, aggregator, activator = None, **kw):
        # I always need to copy this, it turns out, because of
        # how I handle help templates.
        if activator and activator[3]:
            prefix = activator[3]
            o = self._copyForPrefix(prefix)
        elif help_is_template(self.help):
            o = self._copyForPrefix("")
        else:
            o = self
        if activator is not None:
            try:
                aggregator.activationMap[o.dest].add(activator)
            except KeyError:
                aggregator.activationMap[o.dest] = set([activator])
        return o
            
    
#
# OptionGroup
#

# I want to defer to the parser for a number of things, for instance,
# checking the option.

class OptionGroup(optparse.OptionGroup):

    def __init__(self, *args, **kw):
        optparse.OptionGroup.__init__(self, *args, **kw)
        self.phantom_options = set()

    def add_phantom_option(self, op):
        op.phantom_container = self
        self.phantom_options.add(op)

    def format_description(self, formatter):
        # The issue here is that I want to ensure that any newlines I've inserted are preserved.
        desc = self.get_description()
        lines = desc.split("\n")
        return "".join([formatter.format_description(l) or '\n' for l in lines])

    def add_option(self, *args, **kwargs):

        # First step: force the option digestion. This duplicates
        # the work in add_option() in OptionGroup (and I'll have to
        # do the same thing in the parser), but it's cleaner than
        # dealing with the internal APIs.

        if type(args[0]) is types.StringType:
            option = self.option_class(*args, **kwargs)
        elif len(args) == 1 and not kwargs:
            option = args[0]
            if not isinstance(option, Option):
                raise TypeError, "not an Option instance: %r" % option
        else:
            raise TypeError, "invalid arguments"

        return self.parser._add_option(option, group = self)

    def add_activation_option(self, *args, **kw):
        kw["group"] = self
        return self.parser.add_activation_option(*args, **kw)

#
# OptionTemplate
#

# The option template is the internal (or not so internal)
# representation of the options that the optionbearer holds. They
# don't really count as real options yet, not until they're added to the
# parser and activated; this means we can do all sorts of useful things
# about postponing, e.g., figuring out what the list of document IO
# options is.

class OptionTemplate:

    def __init__(self, options, heading = None):
        # Each of the elements in options must be either an Option
        # or an OptionActivation.
        self.options = []
        for o in options:
            if not (isinstance(o, Option) or isinstance(o, OptionActivation)):
                raise TypeError, "neither an option nor an option activation: %s" % o
            self.options.append(o)
        self.heading = heading

    def activate(self, parser, aggregator, **kw):
        # Return a list of options.
        return [o.activate(parser, aggregator, **kw) for o in self.options]

    # This really needs to copy itself, and then add the options, and then return the copy.
    # But that causes another problem elsewhere - if this argument now appears in multiple
    # places, its default is ("NO", "DEFAULT"), because its original default was None.
    
    def __add__(self, o):
        cpy = self.copy()
        if type(o) in (tuple, list):
            # Add the options.
            opts = o
        elif isinstance(o, OptionTemplate):
            opts = o.options
        else:
            raise ValueError, "argument of option template addition is neither an option template nor a sequence of options"
        for o in opts:
            if not (isinstance(o, Option) or isinstance(o, OptionActivation)):
                raise TypeError, "neither an option nor an option activation: %s" % o
            cpy.options.append(o)
        return cpy

    def copy(self, heading = None):
        return OptionTemplate(options = [o.copy() for o in self.options], heading = heading or self.heading)

# This is where lazy activation comes in. It's used for values which
# can be assembled from a tree of OptionBearers, and cause other
# options to be added.

class OptionActivation:

    def __init__(self, optionstr, cls, subtype = None, prefix = None, dest = None, classFilters = None, **kw):
        
        if dest is not None:
            # Because it must be computed by itself.
            raise TypeError, "dest is not permitted in OptionActivation"        

        self.optionstr = optionstr
        self.activationClass = cls
        self.subtype = subtype
        self.classFilters = classFilters
        self.prefix = prefix
        self.kw = kw

    # The stored prefix is the TOPLEVEL prefix. It will not be present anywhere else.
    # So I use it, and only it, to pass down if it's present. I NEVER use it on
    # the optionstr. The prefix that's passed in, on the other hand, I use as the
    # local and recursive prefixes.

    def activate(self, parser, aggregator, activator = None, **kw):
        prefix = None
        if activator is not None:
            prefix = activator[3]
            
        # First, we prep the option name, because we're about to make an option.
        # This is the same thing that happens when we copy for a prefix.
        # Don't put your own prefix on yourself!

        if self.prefix is not None:
            localPrefix = None
            remotePrefix = self.prefix
        else:
            localPrefix = remotePrefix = prefix

        # The information we need to pass to the activation queue is the
        # activator information for this element.

        optionstr = self.optionstr
        dest = self.optionstr[2:]
        if localPrefix:
            optionstr = "--" + localPrefix + optionstr[2:]
            
        # Patch up the help before it gets created.
        if help_is_template(self.kw.get("help")):
            selfKw = kw.copy()
            selfKw["help"] = selfKw["help"] % {"prefix": localPrefix or ""}
        else:
            selfKw = self.kw

        filters = set()
        if self.subtype:
            filters.add(self.subtype)
        if self.classFilters:
            filters.update(self.classFilters)
        choiceDict = self.activationClass.findAll(filters = filters)

        # This only works because choices doesn't check to see if the
        # default is among the choices.
        if selfKw.get("default"):
            selfKw["default"] = choiceDict[selfKw["default"]]
            
        # We want the optionstr, but we also want the original "dest".
        aggregator.activationQueue.append((optionstr, self.activationClass, choiceDict, self.subtype, remotePrefix, dest))
        # We really want the class back.
        o = Option(optionstr, type = "choice", choices = choiceDict.keys(),
                   action = "callback", callback = self._chooseValue,
                   callback_args = (choiceDict, aggregator, optionstr, dest, remotePrefix), **selfKw)
        if activator is not None:
            try:
                aggregator.activationMap[o.dest].add(activator)
            except KeyError:
                aggregator.activationMap[o.dest] = set([activator])
        return o

    def _chooseValue(self, option, opt, value, parser, choiceDict, aggregator, source, dest, prefix):
        oClass = choiceDict[value]
        setattr(parser.values, option.dest, oClass)
        # And, while we're at it, tell the aggregator that
        # this activation happened.
        activator = (source, oClass, dest, prefix)
        aggregator.activatedSet.add(activator)
    

#
# OptionParser
#

class UnactivatedOptionError(optparse.BadOptionError):

    def __str__(self):
        return "unenabled option: %s" % self.opt_str

class _OptionParserRoot(optparse.OptionParser):

    def __init__(self, option_class = Option, **kw):
        self.aggregator = None
        # Make sure that the default option class is my own.
        optparse.OptionParser.__init__(self, option_class = option_class, **kw)

    def add_option(self, *args, **kwargs):
        # First step: force the option digestion. This duplicates
        # the work in add_option() in OptionGroup (and I'll have to
        # do the same thing in the parser), but it's cleaner than
        # dealing with the internal APIs.

        if type(args[0]) is types.StringType:
            option = self.option_class(*args, **kwargs)
        elif len(args) == 1 and not kwargs:
            option = args[0]
            if not isinstance(option, Option):
                raise TypeError, "not an Option instance: %r" % option
        else:
            raise TypeError, "invalid arguments"

        return self._add_option(option)

    # We're going to be forgiving - you can add an option twice, but
    # the second one will be ignored, unless your types don't match,
    # in which case you get an error.

    def _add_option(self, option, group = None):
        
        opt = self.get_option(option.get_opt_string())
        if opt is not None:
            localAction = option.action or "store"
            optAction = opt.action or "store"
            localType = option.type or "string"
            optType = opt.type or "string"
            # Note that in order to do this, we have to be careful, when we define the original
            # Option, not to pass the default key if default is None.
            if (localAction != optAction) or (localType != optType) or (option.default != opt.default):
                raise optparse.OptionError, ("attempt to define multiple options %s with different properties" % option.get_opt_string(), option)
            # Why add this? Because I need it during usage printing.
            # Otherwise, as long as one of them has been added, I
            # don't need another.
            if group is not None:
                group.add_phantom_option(option)
        elif group is not None:
            optparse.OptionGroup.add_option(group, option)
        else:
            optparse.OptionParser.add_option(self, option)

    # classFilters is a list of terms which, along with the subtype, will be
    # passed as filter information to findAll, which can be specialized.
    
    def add_activation_option(self, optionstr, aggregator, activationCls, subtype = None, activatedPrefix = None,
                              group = None, classFilters = None, **kw):
        # This is one of the entry points for lazy activation of a tree of options.
        # We make an option activation, empty the queue, activate the option, and
        # process the queue.
        aggregator.initializeActivationQueue()
        o = OptionActivation(optionstr, activationCls, subtype = subtype, prefix = activatedPrefix, classFilters = classFilters, **kw)
        (group or self).add_option(o.activate(self, aggregator))
        aggregator.processActivationQueue()

    def parse_args(self, *args, **kw):
        values, args = optparse.OptionParser.parse_args(self, *args, **kw)
        # Check to see which options were seen, and whether they
        # were activated.
        if hasattr(values, "_optionsSeen") and self.aggregator:
            for opt in values._optionsSeen:
                needsActivation, activators = self.aggregator.findActivation(opt.dest)
                if needsActivation and (not activators):
                    raise UnactivatedOptionError, opt.get_opt_string()
        return values, args

    def print_help(self, *args, **kw):
        # We have to reconfigure, temporarily, the options and groups
        # here. The only things we should be printing are
        # the things that are activated.
        # So --help will print out only the things which require
        # no activation, plus additional recommendations about what to
        # do for more help. --foo bar --help will print out
        # the things which are enabled by --foo bar.
        # And we have to be sure that we watch to make sure there's
        # an aggregator, because if there isn't, there's no way
        # to do anything besides the normal behavior.
        if not self.aggregator:
            optparse.OptionParser.print_help(self, *args, **kw)
            return
        _cache = {}
        furtherHelp = set()
        allOK = set()
        self._cacheOptionsForHelp(self, _cache, furtherHelp, allOK)
        okGroups = []
        _cachedGroups = self.option_groups
        # So how do we decide if a group has been activated? One of
        # its options needs to have been activated. This INCLUDES
        # phantom elements - otherwise, groups which we accidently
        # empty because their options were described elsewhere
        # wouldn't be listed (and I should make these normal options
        # for the time being).
        for grp in self.option_groups:
            if self._cacheOptionsForHelp(grp, _cache, furtherHelp, allOK):
                okGroups.append(grp)
        self.option_groups = okGroups
        oldEpilog = self.epilog
        trueFurther = (allOK & furtherHelp) - set([activator[0] for activator in self.aggregator.activatedSet])
        if trueFurther:
            self.epilog = "Further help may be available for %s.\nSpecify a value for these options to activate further help." % \
                          ", ".join(trueFurther)
            if oldEpilog:
                self.epilog = oldEpilog + "\n" + self.epilog
        optparse.OptionParser.print_help(self, *args, **kw)
        self.epilog = oldEpilog
        for k, origOptions in _cache.items():
            k.option_list = origOptions
        self.option_groups = _cachedGroups

    # If the source class is in the automatic activations,
    # don't bother checking the option list.
    
    def _cacheOptionsForHelp(self, o, _cache, furtherHelp, allOK):
        okOpts = []
        optList = o.option_list
        if isinstance(o, OptionGroup):
            optList += list(o.phantom_options)
        activate = False
        if o in self.aggregator.automaticActivations:
            okOpts = optList
            # In case there are no options
            activate = True
            allOK.update([opt.get_opt_string() for opt in optList])
        else:
            sourceClass = self.aggregator.sourceClasses.get(o, None)
            for opt in optList:
                # The activators are the ACTUAL things that appear in the
                # command line that cause the group to be shown. So if multiple
                # classes introduced it, the one corresponding to what's on
                # the command line will be present. ONLY that activator
                # counts.
                needsActivation, activators = self.aggregator.findActivation(opt.dest)
                activated = not needsActivation
                if (not activated) and activators:
                    for activator in activators:
                        if activator[1] == sourceClass:
                            activated = True
                            break
                if activated:
                    okOpts.append(opt)
                    allOK.add(opt.get_opt_string())
                else:
                    # Who gets further help? The elements which ARE 
                    # presented which have rejected children.
                    for activator in self.aggregator.activationMap[opt.dest]:
                        furtherHelp.add(activator[0])
        _cache[o] = o.option_list
        o.option_list = okOpts
        return activate or okOpts

# This is the COMMAND-LINE option parser. In order to
# work, it needs to do something hideous and sneaky with the
# boolean type, because nargs is going to be 1. There's a brief
# opportunity in _match_long_opt to add a "yes" or "no" to the
# command line.

# Actually, let's not do that at all. Let's modify option
# instead.

class OptionParser(_OptionParserRoot):

    pass

# Now, we inherit from Option above. We follow the
# following rules. The name we pass to the optparse.Option
# object is "--" + the name. 

class OpArgument(Option):

    def __init__(self, name, hasArg = False,
                 # Now, the attrs for Option.
                 action = None, default = None, type = None, 
                 metavar = None, **attrs):
        
        optparseName = "--" + name
        if action in ["store_const", "count", "append_const"]:
            # We'll follow this up with a way of handling "boolean"
            # as a type. The type will be changed when it gets
            # installed in a parser.
            raise OperationError, "none of store_const, append_const, count are permitted"
        
        if hasArg is False:
            if action is not None:
                raise OperationError, "can't specify action with hasArg = False"
            if type is not None:
                raise OperationError, "can't specify type with hasArg = False"
            action = "store"
            type = "boolean"
            default = False
        elif metavar is None:
            metavar = name.upper()

        # We have to be careful about default. Passing default = None is NOT
        # the same as not passing a value for default. See __add__ in OptionTemplate
        # for the problem.

        if action is not None:
            attrs["action"] = action
        if type is not None:
            attrs["type"] = type
        if metavar is not None:
            attrs["metavar"] = metavar
        if default is not None:
            attrs["default"] = default

        Option.__init__(self, optparseName, **attrs)

        self._matName = name

# Now, option parsers. Neither of these default to the command line.
# For each of these, we stash the args as we're passed them, and return
# [] from get_args, because this will be surgically altered to
# be the final list of nonoption arguments, and neither of these
# have any.

# For both of these, we want to anticipate the possibility that
# we'll be expanding the arguments. So if there's no option yet,
# we should set it aside and return to it later. 

class HashOptionParser(_OptionParserRoot):

    def _add_option(self, option, group = None):        
        # Convert any store_true or store_false options
        # into booleans, right here.
        if option.action in ["store_true", "store_false"]:
            option = option._copyForBoolean()
        return _OptionParserRoot._add_option(self, option, group = group)

    def _process_args(self, largs, rargs, values):

        # For each key, see if the argument is present.
        # If it isn't, return to it later; we may have
        # enhanced the list of arguments. If the loop
        # ever doesn't decrease in length, then we're done.
        keys = self._get_keys()
        lenKeys = len(keys)
        while True:
            if lenKeys == 0:
                return
            nextKeys = []
            for k in keys:
                try:
                    option = self._long_opt["--" + k]
                except KeyError:
                    # Kick it down the road.
                    nextKeys.append(k)
                    continue
                if not option.takes_value():
                    self.error("option '%s' must take a value" % k)
                if option.nargs != 1:
                    self.error("option '%s' requires other than 1 argument" % k)
                v = self._get_value(option)
                self._process_option(option, "--" + k, v, values, self)
            if len(nextKeys) == lenKeys:
                # Actually, at this point, we should just break
                # out of the loop; we want it to ignore the
                # things it doesn't know about, and it's
                # had the chance to do all the progressive
                # enhancement it wants to.
                # raise optparse.BadOptionError(nextKeys[0])
                break
            keys = nextKeys
            lenKeys = len(keys)

    def _process_option(self, option, opt, value, values, parser):
        option.process(opt, value, values, parser)

class DictOptionParser(HashOptionParser):

    def __init__(self, *args, **kw):
        HashOptionParser.__init__(self, *args, **kw)
        self.dictInput = None

    def _get_args(self, args):
        self.dictInput = args
        return []

    def _get_keys(self):
        return self.dictInput.keys()

    def _get_value(self, option):
        return self.dictInput[option._matName]

    def _process_option(self, option, opt, value, values, parser):
        # We don't want to convert the value; we go directly to
        # take_action, and then _after_process.
        r = option.take_action(option.action, option.dest, opt, value, values, parser)
        option._after_process(value, values, parser)
        return r        
        
class XMLOptionParser(HashOptionParser):

    def __init__(self, *args, **kw):
        HashOptionParser.__init__(self, *args, **kw)
        self.xmlInput = None            

    def _get_args(self, args):
        self.xmlInput = args
        return []

    def _get_keys(self):
        return self.xmlInput.keys()

    def _get_value(self, option):
        return self.xmlInput[option._matName]

class CGIOptionParser(HashOptionParser):
    def __init__(self, *args, **kw):
        HashOptionParser.__init__(self, *args, **kw)
        self.cgiInput = None

    def _get_args(self, args):
        self.cgiInput = args
        return []

    def _get_keys(self):
        return self.cgiInput.keys()

    def _get_value(self, option):
        if option.action == "append":
            return self.cgiInput.getlist(option._matName)
        else:
            return self.cgiInput.getfirst(option._matName)

# We want this to be a state machine, basically. But we have to
# tackle the issue of how to manage it when it's a commandline.

# So basically, this guy needs to keep track of its state.
# It's initialized possibly with values, possibly with a parser.

class OpArgumentAggregator:

    parserClass = None

    def __init__(self, inputs, parser = None, values = None):
        self.inputs = inputs
        # Values is an option object, if provided.
        self.values = values
        self.parser = parser
        # This is the queue of activations.
        self.activationQueue = []
        # This is the record of what's already been
        # activated, so you don't do it more than once.
        self.activationRecord = {}
        # This is the mapping from destinations to activations.
        self.activationMap = {}
        self.activatedSet = set()
        if self.parser:
            self.parser.aggregator = self

    def _getParser(self):
        if not self.parser:
            self.parser = self.parserClass()
            self.parser.aggregator = self
        return self.parser

    def _getValues(self, defaults = None):
        if not self.values:
            values = None
            parser = self._getParser()
            if defaults is not None:
                # We need to ensure that the side effect callbacks are called.
                # In order to do that, we call a DictOptionParser on the defaults.
                # And we have to rescue the arguments which are added, and
                # add them to the current parser. Grrr.                
                p = DictOptionParser()
                p.aggregator = self
                for o in parser._get_all_options():
                    p.add_option(o)
                values, ignore = p.parse_args(defaults)
                # Now, REUSE THE VALUES. We'll end up with all the values
                # in the right place.
                for o in set(p._get_all_options()) - set(parser._get_all_options()):
                    parser.add_option(o)
            self.values = parser.parse_args(self.inputs, values = values)[0]
        return self.values

    # Instead of being initialized with an option object
    # (which isn't possible sometimes), we initialize with a parser,
    # store the option later, and disable addOptions,
    # because it should have already happened. The only
    # use of this so far in the system is in MATWorkspaceEngine,
    # where the operations are parsed and later augmented with
    # operation settings.
    
    def storeValues(self, values):
        self.values = values

    # This can be called numerous times, and it should be a no-op
    # if the values have already been created.

    # If there's a prefix, I need to duplicate the argument, but
    # keep the SAME DEST.

    # If we're doing progressive enhancement, and we're adding an
    # option, we'd better add the default to the values.

    # Nixing the progressive enhancements. Instead, addOptions knows
    # how to deal with a queue of things to activate. So this is the
    # main entry point. No one should be calling this except at
    # the toplevel.
    
    def addOptions(self, cmdArgs, group = None, values = None, **kw):
        if cmdArgs and (self.values is None):
            for arg in cmdArgs:
                if group:
                    group.add_option(arg)
                else:
                    self._getParser().add_option(arg)
                if values is not None:
                    # We KNOW we don't have it yet. Adding it is cheap.
                    setattr(values, arg.dest, arg.default)

    def initializeActivationQueue(self):
        self.activationQueue = []
        self.activationRecord = set()
        
    def processActivationQueue(self):
        while self.activationQueue:            
            source, cls, cDict, subtype, prefix, dest = self.activationQueue[0]
            self.activationQueue[0:1] = []
            recordKey = (cls, subtype, prefix)
            if recordKey in self.activationRecord:
                continue
            self.activationRecord.add(recordKey)
            for vname, oClass in cDict.items():
                activator = (source, oClass, dest, prefix)
                oClass._addOptions(self, activator = activator, 
                                   heading_suffix = (source and " (via %s %s)" % (source, vname)) or None,
                                   subtype = subtype)

    def findActivation(self, dest):        
        needsActivation = self.activationMap.has_key(dest)
        if needsActivation:
            return True, (self.activationMap[dest] & self.activatedSet)
        else:
            return False, None

    def extract(self, reportDefaults = False, defaults = None):
        if self.values is None:
            # Use it in getting the values. But also we need to be able to pass through
            # any defaults which weren't digested. I'm pretty sure reusing defaults
            # in both places will get me this. The engine default tests pass, and
            # that's a good sign.
            return self.convertToKW(self._getValues(defaults = defaults), reportDefaults = reportDefaults, defaults = defaults)
        else:
            # Use it in extracting the kw.
            return self.convertToKW(self._getValues(), reportDefaults = reportDefaults, defaults = defaults)

    # Make sure that all the defaults are appropriately reported.
    # Don't want to return [] in a situation where it might be
    # altered.

    # We can pass defaults to convertToKW, and they won't get
    # salted into the values, unlike extract() above. reportDefaults
    # means to report the defaults from the OPTIONS.
    
    def convertToKW(self, values, reportDefaults = False, defaults = None):
        # If reportDefaults is False, then make sure the option
        # has been optionsSeen if the value is not None. If reportDefaults
        # is True, then make sure the proper defaults are provided.
        if defaults:
            optArgs = defaults.copy()
        else:
            optArgs = {}
        allKeys = dict([(arg.dest, arg) for arg in self.parser._get_all_options()
                        if arg.dest is not None])
        optsSeen = None
        if hasattr(values, "_optionsSeen"):
            optsSeen = values._optionsSeen
        # The optArgs respect the prefixes on the activators on the options.
        for arg, obj in allKeys.items():
            v = getattr(values, arg, None)
            # We actually have to make sure that when we retrieve the
            # value, we make sure that we rule out optparse.NO_DEFAULT.
            if v is optparse.NO_DEFAULT:
                v = None
            recordValue = False
            if v is not None:
                if reportDefaults or (optsSeen and (obj in optsSeen)):
                    recordValue = True
                    optArgs[arg] = v
            elif reportDefaults:
                if obj.type == "boolean":
                    v = True
                elif obj.action == "append":
                    v = []
                recordValue = True
            if recordValue:
                container = optArgs
                needsActivation, activators = self.findActivation(arg)
                if needsActivation:
                    activator = activators.pop()
                    source, oClass, dest, prefix = activator
                    if prefix is not None:
                        containerName = prefix
                        arg = arg[len(prefix):]
                        try:
                            container = optArgs[containerName]
                        except KeyError:
                            container = {}
                            optArgs[containerName] = container
                container[arg] = v
        return optArgs

    # This method used to be on the OptionBearer, but in the new
    # regime, it has to be here. It's also used ONLY in enhanceAndValidate,
    # which itself is only used once. DO NOT USE THIS FURTHER.
    # I'm exploiting the fact that it only adds arguments from a single
    # class to be able to ignore the fact that the classes no longer
    # know what arguments they yielded.
    
    # We used to check obligatorihood, but no one was using it
    # so I killed it. 
    
    def validate(self, cls, **argDict):
        
        # argDict is a dictionary, where the
        # values are either strings, lists of strings, or
        # booleans.

        argsByKw = {}
        for o in self.parser._get_all_options():
            argsByKw[o._matName] = o

        for arg, val in argDict.items():
            try:
                argObj = argsByKw[arg]
            except KeyError:
                # The argument may not exist, in which case we skip it.
                # We used to barf, but now we're accumulating lots of
                # arguments, possibly for multiple commandline engine steps.
                continue
            
            # This may raise an operation error.
            self._argValidate(argObj, val)

        return argDict
    
    #
    # This is special for the use of validate() in the option bearer below.
    # 

    def _argValidate(self, option, val):
        if val is None:
            if option.action == "append":
                raise OperationError, ("option %s default must be []" % option._matName)
            else:
                return
        # Prepare for testing all vals.
        if option.action != "append":
            valList = [val]
        else:
            valList = val
        for val in valList:
            err = None
            if option.type == "boolean":
                if val not in [True, False]:
                    err = "True or False"
            elif option.type == "int":
                if type(val) is not int:
                    err = "an integer"
            elif option.type == "float":
                if type(val) is not float:
                    err = "a float"
            elif option.type == "string":
                if type(val) not in [str, unicode]:
                    err = "a string"
            elif option.type == "complex":
                if type(val) is not complex:
                    err = "a complex number"
            elif option.type == "long":
                if type(val) is not long:
                    err = "a long integer"
            elif option.type == "choice":
                if val not in option.choices:
                    err = "one of the strings " + ", ".join(["'"+a+"'" for a in option.choices])
            if err:
                if option.action == "append":                    
                    raise OperationError, ("each value of option %s must be %s" % (option._matName, err))
                else:
                    raise OperationError, ("the value of option %s must be %s" % (option._matName, err))

# This one is the exception, because it interacts with the parser
# options, and the addOptions method needs to set things up for
# parsing command lines, which requires more information than usual.

class CmdlineOpArgumentAggregator(OpArgumentAggregator):

    def __init__(self, parser):
        OpArgumentAggregator.__init__(self, None, parser = parser)
        self.sourceClasses = {}
        self.automaticActivations = set()
        
    # Right now, we're using this for the workspaces,
    # where groups are created for each folder action in some cases.
    # And sometimes they don't have options.
    
    def forceActivation(self, group):
        self.automaticActivations.add(group)

    def addOptions(self, cmdArgs, name = None, heading = None, group = None, description = None, source_class = None, **kw):
        if cmdArgs and (self.values is None):
            if group is None:
                # I'm not using the name in the PluginStep case, because I'm updating
                # the title of the group later.
                if heading is None:
                    heading = "Arguments for the '%s' operation" % (name or "",)
                group = OptionGroup(self.parser, heading)
                self.sourceClasses[group] = source_class
                if description is not None:
                    group.set_description(description)
                # Add it FIRST.
                self.parser.add_option_group(group)
            OpArgumentAggregator.addOptions(self, cmdArgs, group = group, **kw)

# The CGI form is what gets stored when this is created.

class CGIOpArgumentAggregator(OpArgumentAggregator):

    parserClass = CGIOptionParser

class XMLOpArgumentAggregator(OpArgumentAggregator):

    parserClass = XMLOptionParser

# What about sharing arguments on the command line?
# The problem arises only when multiple operations
# need the same value, but the interpretation of that
# value is different. How do we deal with that?
# Let's add operation name prefixes.

# One more thing: I think I'm going to set things up
# so that you can instantiate separate instances of operations.
# That is, all the argument information will be CLASS information
# now, and addOptions will be a class method.
# That way, we can have the class operation still
# able to add options to the command line, if desired,
# and the individual operations can hold state. If desired.

class OptionBearer(object):

    @classmethod
    def _getInstantiableName(cls):
        # Ugh. This is so horrid. We can find local declarations
        # by looking at __dict__ of the class. This does NOT
        # include inheritance.
        if (not cls.__dict__.has_key("instantiable")) or (cls.__dict__["instantiable"] is True):
            if cls.__dict__.has_key("ov_name"):
                return cls.__dict__["ov_name"]
        return None

    @classmethod
    def findAll(cls, d = None, filters = None):
        if d is None: d = {}
        n = cls._getInstantiableName()
        if n is not None:
            d[n] = cls
        for subCls in cls.__subclasses__():
            subCls.findAll(d = d)
        return d        

    name = None

    # This should be a list of OpArgument elements.
    # argList = []

    @classmethod
    def _ensureArgs(cls, argVar = "args", **kw):
        # I can't use hasattr(), because hasattr() inherits,
        # and I want this to be entirely local. The only
        # way I know of to guarantee this to look at the dict.
        # Actually, I can also use private variables, and
        # apparently, they work just as well for private
        # class variables.
        # Actually, I can also use __dict__. And I only
        # generate from _argList if argSubtype is the default.
        # Well, actually, I can't use __dict__ to set
        # elements; it's got to be via the attr.
        # And at this point, I want to inherit.
        # Actually, no. If you have argList or _createArgList,
        # you should use it if (a) it's local or (b)
        # you don't have a local args.
        if argVar == "args":
            if hasattr(cls, "_createArgList"):
                if cls.__dict__.has_key("_createArgList") or (not cls.__dict__.has_key("args")):
                    try:
                        heading = cls.argListHeading
                    except AttributeError:
                        heading = None
                    cls.args = OptionTemplate(cls._createArgList(), heading = heading)
            elif hasattr(cls, "argList"):
                if cls.__dict__.has_key("argList") or (not cls.__dict__.has_key("args")):
                    try:
                        heading = cls.argListHeading
                    except AttributeError:
                        heading = None
                    cls.args = OptionTemplate(cls.argList, heading = heading)                    

        # 
        #    cls.__args = {}
        #    cls.argsByKw = {}
        #    for arg in argList:
        #        cls.__args[arg._matName] = arg
        #        cls.argsByKw[arg.dest] = arg

    # We're going to force everyone who
    # uses Operations to use the new optparse
    # module. It also needs to be called
    # recursively on all the operations.

    # And although it's the aggregator that accumulates things,
    # this is the entry point for the recursive activation.    

    @classmethod
    def addOptions(cls, aggregator, subtype = "args", heading = None, **kw):
        aggregator.initializeActivationQueue()
        cls._addOptions(aggregator, subtype = subtype, heading = heading, **kw)
        aggregator.processActivationQueue()

    @classmethod
    def getOptionTemplate(cls, subtype = "args"):
        cls._ensureArgs(argVar = subtype)
        if hasattr(cls, subtype):
            args = getattr(cls, subtype)
            if args:
                if callable(args):
                    args = args()
                if isinstance(args, OptionTemplate):
                    return args
        return None


    # This is the element that all calls besides the toplevel should make.
    @classmethod
    def _addOptions(cls, aggregator, subtype = "args", heading = None, heading_suffix = None, **kw):
        args = cls.getOptionTemplate(subtype = subtype)
        if isinstance(args, OptionTemplate):
            if heading is None:
                heading = args.heading
                if heading and (heading_suffix is not None):
                    heading = heading + heading_suffix
            aggregator.addOptions(args.activate(aggregator.parser, aggregator, **kw),
                                  # This will only be used in the cmdline.
                                  source_class = cls,
                                  name = cls.name, heading = heading, **kw)

    def __init__(self):
        # The method will be automatically called
        # on the class, because it's a class method.
        self._ensureArgs()

    # Introduce a special case for when the aggregator is actually
    # already an extracted dictionary.

    # The params are treated as defaults; the aggregator contents
    # get whomped on top of them.

    @classmethod
    def enhanceAndValidate(cls, aggregator, reportDefaults = False, **params):
        if aggregator is not None:
            cls.addOptions(aggregator)
            params = aggregator.extract(reportDefaults = reportDefaults, defaults = params or None)
            # I used to call validate() on the OptionBearer, but the fact is that
            # the option bearer no longer has all the arguments; it may have an
            # OptionActivation which is a promise to add more arguments. So I can no longer
            # really tell which argument belongs to which item - and I mostly don't
            # need to, because everyone who makes use of this mechanism use **kw
            # and I've made sure that arguments can't clash. And anyway, validate()
            # method is only used here, and this method is currently only called in
            # _runOperation() in Workspace.py, which means it's fed only by the
            # operation. Short of getting rid of this entirely, the easiest thing
            # to do is to move this method to the aggregator, and ignore where
            # the options came from.
            # There's the additional problem that the aggregator may not exist.
            return aggregator.validate(cls, **params)
        # Without an aggregator, I'm going to skip the WFC check.
        return params

    @classmethod
    def enhanceAndExtract(cls, aggregator, reportDefaults = False, **params):
        cls.addOptions(aggregator)
        return aggregator.extract(reportDefaults = reportDefaults, defaults = params or None)

class Operation(OptionBearer):

    # By the time we get to "do", the arguments
    # should already have been vetted. The **args
    # should be the postprocessed dictionary that
    # is the output of validate.

    def do(self, *args, **kw):
        pass
