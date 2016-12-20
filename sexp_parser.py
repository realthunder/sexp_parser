'''
S-Expression parser written in Python

This module provides a generic parser `SexpParser` that coverts a python
list-based S-Expression into a python object model.  Each expression in the
list-based S-Expression is defined as a recursive ``list`` representation in
the form of ::

    [ <line number>, <key>, <value>... ]

where there may be none or multiple ``<values>`` of either an atom or another
list based S-Expression. The class `Sexpression` is top class for objects
representing a parsed expresion

function `parseSexp()` can be used to convert plain text form S-Expression into
the list-based representation

'''

import re
import logging
import traceback
import bisect
from collections import OrderedDict

__author__ = "Zheng, Lei"
__copyright__ = "Copyright 2016, Zheng, Lei"
__license__ = "MIT"
__version__ = "1.0.0"
__email__ = "realthunder.dev@gmail.com"
__status__ = "Prototype"

logger = logging.getLogger(__name__)

class SexpValueDict(OrderedDict):
    '''Dictionary for holding named and un-named values

        The order of appearance may be significant in certain S-Expression,
        which is why we use ``OrderedDict`` here.
    '''

    __slots__ = '_idx'

    def __init__(self):
        super(SexpValueDict,self).__init__()
        self._idx = 0

    def add(self,sexp, action=3):
        '''Add an S-Expression value
            
            Args:
                sexp (`Sexpression`): S-Expression value to be added
                action (int): action to take when an storing an S-Expression
                              Acceptable values are,
                              
                    * 0: overwrite if there one with the same key
                    * 1: throw exception if there one with the same key
                    * 2: always use `SexpList`
                    * 3: dynamic change to `SexpList` if there is more than 
                         one with the same key

            If ``sexp._key`` is None, than an internal index will be assigned
            as the key indicating that this S-Expression is un-named, and is
            keyed by its position, kinda like positional based command line
            options
        '''
        if not isinstance(sexp,Sexpression):
            raise TypeError('expects type Sexpression')

        if sexp._key is None:
            sexp._key = self._idx
            self._idx += 1

        if action==0:
            self[sexp._key] = sexp
            return

        if sexp._key not in self:
            if action==2:
                sexp = SexpList(sexp._key,[sexp])
            self[sexp._key] = sexp
            return

        if action==1:
            logger.error(self)
            raise KeyError('duplicate key {}'.format(sexp._key))
        elif action!=2 and action!=3:
            raise ValueError('unknown action')

        v = self[sexp._key]
        if isinstance(v,SexpList):
            v._append(sexp)
            return
        self[sexp._key] = SexpList(sexp._key,[v,sexp])

    def __str__(self):
        return str(self.keys())
        

class Sexpression(object):
    '''Generic class to represent a S-Expression

        Attributes:
            _key (string|int): hold the key of this S-Expression
            _value: various types for present the value of this expression

        This class provides the basic accessing interface for sub-keys, and
        sub-values of an expression. It also has the `_export()` function to
        export back the plain S-Expression text form

        Subclasses are advised to use only attributes start with '_'.
        Non-underscored attributes are reserved for accessing named values (i.e.
        sub S-Expressions)
    '''
    __slots__ = '_key','_value'

    def __init__(self,key,value):
        self._key = key
        self._value = value

    def __len__(self):
        return len(self._value)

    def __getitem__(self,key):
        v = self._value[key]
        if hasattr(v,'__get__'):
            return v.__get__(self,self.__class__)
        elif isinstance(v,Sexpression) and \
            not hasattr(v._value,'__getitem__'):
            return v._value
        return v

    def __setitem__(self,key,value):
        if not isinstance(value,Sexpression):
            self._value.add(Sexpression(key,value))
        elif value._key != key:
            raise KeyError('key mismatch')
        else:
            self._value.add(value)

    def __delitem__(self,key):
        del self._value[key]

    def __str__(self):
        return str(self._value)

    def __getattr__(self,name):
        try:
            if not name.startswith('_'): 
                return self.__getitem__(name)
        except KeyError: pass
        raise AttributeError

    def __delattr__(self,name):
        if name.startswith('_'): 
            delattr(self,name)
            return
        try:
            return self.__delitem__(name)
        except KeyError:
            raise AttributeError

    def __setattr__(self,name,value):
        if name.startswith('_'):
            super(Sexpression,self).__setattr__(name,value)
            return
        try:
            return self.__setitem__(name,value)
        except KeyError:
            raise AttributeError

    def __iter__(self):
        for v in iter(self._value):
            yield v

    def _export(self, out, prefix='', indent='  '):
        '''Export self to an S-epression and write to output stream
            Args: 
                out: output stream, only needs to implement ``out.write(string)``
                prefix(string): prefixing spaces for output formating 
                indent(string): incremental prefix for sub levels
        '''

        if self._value is None:
            out.write(' {}'.format(self._key))
            return

        export_key_ = isinstance(self._key,basestring)
        if export_key_:
            out.write('\n{}({}'.format(prefix,self._key))
            prefix += indent

        try:
            p = getattr(self._value,'_export',None)
            if p is not None:
                p(out,prefix,indent)
            elif isinstance(self._value,basestring) or \
                    not hasattr(self._value,'__iter__'):
                out.write(' {}'.format(self._value))
            else:
                for v in (self._value if isinstance(self._value,list) \
                        else self._value.values()):
                    self._exportValue(out,v,prefix,indent)
                        
        except Exception as e:
            logger.error((len(prefix)/len(indent),self.__class__.__name__,self._key,str(e)))
            if logger.isEnabledFor(logging.ERROR):
                traceback.print_exc()

        if export_key_:
            out.write(')')

    def _exportValue(self,out,value,prefix,indent):
        '''Called by `_export()` to export each indivdual value

            It tries ``value._export()`` before fallback to str(value) Subclass
            can override this method to customize the behavior
        '''
        p = getattr(value,'_export',None)
        if p is not None:
            p(out,prefix,indent)
        else:
            out.write(' {}'.format(value))


class SexpList(Sexpression):
    '''Used to contain a list of expression with the same key

        When exporting, it will not export its own key, but export all of its
        children under at the current level
    '''

    __slots__ = ()

    def __init__(self,key,*args):
        super(SexpList,self).__init__(key,[])
        self._append(list(*args))

    def _export(self,out,prefix='',indent='  '):
        for v in self._value:
            self._exportValue(out,v,prefix,indent)

    def __str__(self):
        return '<list>:{}'.format(len(self._value))

    def _append(self,sexp):
        if isinstance(sexp,SexpList):
            sexp = sexp._value
        elif isinstance(sexp,Sexpression):
            if sexp._key != self._key:
                raise KeyError('expceting key {}'.format(self._key))
            self._value.append(sexp)
            return
        elif not isinstance(sexp,(list,tuple)):
            raise TypeError

        # recursive expansion of any SexpList inside sexp
        for v in sexp:
            self._append(v)
        

class SexpParser(Sexpression):
    """Basic parser class

        The parser expects input data to be a python ``list`` representation of
        the S-expression, i.e. a recurisve list of form ::

            [ <line number>, <key>, <value>... ]

        where it can have zero or more ``<value>`` of either signleton type or
        another ``list`` of the same format.
        
        The parser uses the constructor to dispatch lower level parsers.
    """

    __slots__ = '_err'

    def __init__(self,data):
        '''Constructor that dispatches parsing to lower level parsers

            Args: 
                data (string|list): if data is a list, it holds the S-Expression
                                    to be parsed with the following form ::

                    [ <line number>, <key>, <value>...]

                where each ``<value`` may be another list of the same form. 
                
            If `data` is a string, then it is a value without key.
            ``self._key`` will be set ``None``, and will be assigned an integer
            index after being added to parent's value dictionary of type
            `SexpValueDict`

            The constructor will dispatch keyword parsing to lower level
            parsers grouped by ``self`` here. User impelements semantic check
            by subclassing this class, and provides, for each sub-keys, a
            sub-parser as callable attributes. The search is done in the
            following order,

            * Sub-parsers named as ``_pos<index>`` are called to handle
              positional based expression, ``<index>`` is the occurance index of
              this sub-expression inside the parent expression

            * Sub-parses named as ``_parse1_<subkey>`` demand that the
              corresponding key must not appear more than once

            * Sub-parsers named as ``'_parse_<subkey>`` causes the result to be
              always store into a list (i.e. type ``SexpList``)

            * ``<key>`` value appread in an attribute ``_default_bools`` are
              parsed using `SexpDefaultTrue`. Any missing expression with keys in
              ``_default_bools`` will be append as a ``False`` value

            * If no subparser is found, `self._parse()` as fallback

            Lower level parser can bypass result storage by not returning
            anything, and perform its own storage
        '''

        super(SexpParser,self).__init__(data[1],SexpValueDict())

        self._err = []

        bools = getattr(self,'_default_bools',None)
        if bools is None:
            bools = []
        elif isinstance(bools,basestring):
            bools = [bools]
        elif not isinstance(bools,set):
            bools = set(bools)

        log = logger.isEnabledFor(logging.INFO)

        for i,entry in enumerate(data[2:]):
            try:
                if not isinstance(entry,list):
                    subkey = entry
                else:
                    subkey = entry[1]

                parse = getattr(self,'_pos{}_parse'.format(i),None)
                if parse is not None:
                    if log: logger.info('{}._pos{}_parse {}'.format(self.__class__.__name__,i,entry))
                    action = 3 # dynamic change to SexpList
                else:
                    parse = getattr(self,'_parse1_{}'.format(subkey),None)
                    if parse is not None:
                        if log: logger.info('{}._parse1_{} {}'.format(self.__class__.__name__,subkey,entry))
                        action = 1 # force one instance, and raise error if not
                    else:
                        action = 2 # always use SexpList even if there is only one instance
                        parse = getattr(self,'_parse_{}'.format(subkey),None)
                        if parse is not None:
                            if log: logger.info('{}._parse_{} {}'.format(self.__class__.__name__,subkey,entry))
                        elif subkey in bools:
                            parse = SexpDefaultTrue
                            action = 1
                            if log: logger.info('{}._default_bools {}'.format(self.__class__.__name__,entry))

                if parse is None:
                    action = 3 # dynamic change to SexpList
                    if log: logger.info('{}._parse {} {}'.format(self.__class__.__name__,i,entry))
                    ret = self._parse(i,entry)
                else:
                    ret = parse(entry)

                if ret is not None:
                    self._addValue(ret,action)

            except Exception as e:
                if isinstance(entry,basestring):
                    self._err.append((str(e),entry,data))
                else:
                    self._err.append((str(e),entry))
                logger.error(self._err[-1])
                if log: traceback.print_exc()

        for k in bools:
            if k not in self._value:
                self._value[k] = SexpDefaultTrue(k,False)

    def _getError(self):
        '''Returns a list of errors'''
        ret = []
        for v in iter(self._value):
            try:
                p = getattr(v,'_getError',None)
                if p is None: continue
                r += p()
            except: pass
        ret += self._err
        return ret

    def _addValue(self,sexp,action):
        '''Called by `__init__()` to add each individual parsed value

            Args:
                sexp (`Sexpression`): parsed result
                action: See `SexpValueDict.add()` for possible values
        '''
        self._value.add(sexp,action)

    def _parse(self,idx,value):
        '''Called by `__init__()` as a fallback

            Args:
                idx (int): index position of this value in its parent
                           expression
                value: the value to parse
        '''
        return parseDefault(self,value)


class SexpBool(Sexpression):
    '''Parser for parsing boolean type value

        The constructor treat the following string value as ``True`` :: 
            'yes', 'Yes', 'true', 'True'

        and ``False`` ::
            'no', 'No', 'false', 'False'

        The actual text representation is stored in ``_value``, and boolean
        value is computed at runtime by checking agains the ``_yes_values``
    '''

    __slots__ = ()
    
    _yes_values = ['yes','Yes','True','true']
    _no_values = ['no','No','False','false']

    def __init__(self,data):
        if isinstance(data,basestring):
            key = None
            value = data
        elif not isinstance(data,list) or len(data)!=3:
            raise ValueError('invalid boolean expression')
        else:
            key = data[1]
            value = data[2]

        if value not in _yes_values and \
            value not in _no_values:
            raise ValueError('invalid boolean value')
        super(SexpBool,self).__init__(key,value)

    def __nonzero__(self):
        return self._value in _yes_values

    def __bool__(self):
        return self.__nonzero__()

    def _export(self,out,prefix='',indent='  '):
        out.write('\n{}({} {})'.format(prefix,self._key,self._value))

    def _toggle(self):
        if bool(self):
            self._value = _no_values[_yes_values.index(self._value)]
        else:
            self._value = _yes_values[_no_values.index(self._value)]

    def __set__(self,instance,value):
        if isinstance(value,basestring):
            if value not in _yes_values and \
                value not in _no_values:
                raise ValueError('invalid boolean value')
            self._value = value
        elif bool(value) != bool(self):
            self._toggle()

    def __get__(self,instance,owner):
        return bool(self)

    def __str__(self):
        return self._value


class SexpDefaultTrue(Sexpression):
    '''Converts an un-named value to a named value of boolean value ``True``
        
        For an expression such as ``drill(oval 1 2)``, `oval` is normally
        treated as an un-named string value. However, some semantics may
        interpret it as a boolean value of ``True`` with key 'oval'. And
        missing such value will indicate as ``False``. 
        
        This class can be used to implement such semantics. Simply add a
        keyword into a class variable called `_default_bool` of your subclass
        of `SexpParser`. Any value with the keyword will behavior as described
        above.
    '''
    __slots__ = ()

    def __init__(self,data,value=True):
        if not isinstance(data,basestring):
            raise ValueError('invalid boolean data')
        super(SexpDefaultTrue,self).__init__(data,value)

    def __nonzero__(self):
        return self._value

    def _export(self,out,prefix='',indent='  '):
        if self._value:
            out.write(' '+self._key)

    def __str__(self):
        return str(self._value)

    def _toggle(self):
        self._value = not self._value

    def __set__(self,instance,value):
        self._value = bool(value)

    def __get__(self,instance,owner):
        return bool(self)

######################################################################################
# Parser helper functions

def parseDefault(obj,sexp):
    '''Default handling of value parsing

        Arg:
            sexp: the value for parsing

        Returns an Sexpression object for `SexpParser` to store the value

        This function will try to guess the value format by trying type
        conversion of ``int, float and SexpBool. It will use `SexpParser` to
        parse any composite expressions, i.e. if there is any ``list`` type
        element inside ``sexp``
    '''

    if isinstance(sexp,basestring):
        try:
            return Sexpression(None,int(sexp));
        except: pass
        try:
            return Sexpression(None,float(sexp));
        except: pass
        return Sexpression(None,sexp)

    try:
        return SexpBool(self,sexp)
    except: pass

    if len(sexp) < 2:
        raise ValueError('no key')
    value = []
    for v in sexp[2:]:
        if isinstance(v,list):
            return SexpParser(sexp)
        try:
            value.append(int(v))
            continue
        except: pass
        try: 
            value.append(float(v))
            continue
        except: pass
        value.append(v)
    if not len(value):
        value = None
    elif len(value)==1:
        value = value[0]
    return Sexpression(sexp[1],value)
            

def parseNone(obj,sexp):
    """Discards the value"""
    pass

def parseAtom(obj,sexp,ftype=None):
    if not isinstance(sexp,basestring):
        raise ValueError('expects an atom')
    if ftype is not None:
        sexp = ftype(sexp)
    return Sexpression(None,sexp)

def parseAtomInt(obj,sexp):
    return parseAtom(obj,sexp,int)

def parseAtomFloat(obj,sexp):
    return parseAtom(obj,sexp,float)

def parseCopy(obj,sexp,checkLen,ftype=None):
    """Returns the value and check the length, optionally conver to another
    type"""
    if len(sexp)!=checkLen+2:
        raise ValueError('len={}, expects {}'.format(len(sexp),checkLen+2))
    if ftype is None:
        return Sexpression(sexp[1],sexp[2:])
    else:  
        return Sexpression(sexp[1],[ftype(v) for v in sexp[2:]])

def parseCopy1(obj,sexp):
    return parseCopy(obj,sexp,1)

def parseInt1(obj,sexp):
    return parseCopy(obj,sexp,1,int)

def parseFloat1(obj,sexp):
    return parseCopy(obj,sexp,1,float)

def parseFloat2(obj,sexp):
    return parseCopy(obj,sexp,2,float)

def parseFloat3(obj,sexp):
    return parseCopy(obj,sexp,3,float)

def parseFloat4(obj,sexp):
    return parseCopy(obj,sexp,4,float)

def parseSexp(sexp):
    """Parses S-expressions and return a ``list`` represention
        
        Code borrowed from: http://rosettacode.org/wiki/S-Expressions, with
        the following modifications,

        * Do not parse numbers
        * Do not strip quotes (for easy export back to S-expression)
        * Added line number information for easy debugging
    """

    if not hasattr(parseSexp,'regex'):
        parseSexp.regex = re.compile(
            r'''(?mx)
                    \s*(?:
                    (?P<l>\()|
                    (?P<r>\))|
                    (?P<q>"[^"]*")|
                    (?P<s>[^(^)\s]+)
                )''')

    # Pre-process data to get index position of each line end
    lines = []
    count = 0
    if isinstance(sexp,basestring):
        sexp = sexp.splitlines(False)
    for l in iter(sexp):
        count += len(l)
        lines.append(count)
    sexp = ''.join(sexp)

    stack = []
    out = []
    if logger.isEnabledFor(logging.DEBUG):
    	logger.debug("%-6s %-14s %-44s %-s" % tuple("term value out stack".split()))
    for termtypes in re.finditer(parseSexp.regex, sexp):
        term, value = [(t,v) for t,v in termtypes.groupdict().items() if v][0]
    	if logger.isEnabledFor(logging.DEBUG):
	    logging.debug("%-7s %-14s %-44r %-r" % (term, value, out, stack))
        if   term == 'l': # left bracket
            stack.append(out)
            out = []
        elif term == 'r': # right bracket
            assert stack, "Trouble with nesting of brackets"
            tmpout, out = out, stack.pop(-1)
            out.append(tmpout)
        else:
            if not out: 
                # insert line number as the first element
                out.append(bisect.bisect_right(lines,termtypes.start()))
            if term == 'q': # quoted string
                # out.append(value[1:-1]) # strip quotes
                out.append(value) # do not strip quotes
            elif term == 's': # simple string
                out.append(value)
            else:
                raise NotImplementedError("Error: %r" % (term, value))

    assert not stack, "Trouble with nesting of brackets"

    if not out: return []
    return out[0]

def exportSexp(sexp, out, prefix='', indent='  '):
    if not isinstance(sexp,Sexpression):
        sexp = Sexpression(None,sexp)

    if isinstance(out,basestring):
        with open(out,'w') as f:
            sexp._export(f,prefix,indent)
    else:
        sexp._export(out,prefix,indent)

def getSexpError(sexp):
    p = getattr(sexp,'_getError',None)
    return p()
