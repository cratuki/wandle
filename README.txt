#
# Wandle
#

Pitch: Architectural Design Language for sketching asynchronous systems.


// Overview

This is a tool for designing systems.

Motive

    As a data model grows, it becomes difficult for a single human to fit it
    all in their head.

    If you are designing a system, it is easy to find massaging the model in
    order to serve one use-case, whilst accidentally breaking three other
    use-cases in the background.

    This tool compiles all of your use cases against a single data model.

    In this way, it allows mortals to design sophisticated asynchronous
    systems.

Usage

    Describe a data model in a Wandle Document.

    Add use-cases ('flows').

    Compile the document.

If the compiler does not complain, it indicates that your data model is
internally consistent.

Potentially we could have the compiler build sequence diagrams of each of
the use-cases, but we have not yet done that.


// Setup

From the base directory,

    # Create a python virtual env
    python3 -B -m venv venv

    # Activate the venv (Linux)
    . venv/bin/activate

    # Install the libraries we need
    pip install -r requirements.txt

    # Run the tool against the sample document
    python3 -B -m wandle.main `pwd`/doc/sample.wandle

There is a convenience script for lauching, app.


// Example of a Wandle Document

# Note: type Void is implicit.

# "Stubbed" classes
class Int;
class String;

generic List ITEM {
    sync Void add(ITEM item);
    sync ITEM get(Int int);
}

generic Map K,V {
    sync Void put(K k, V v);
    sync V get(K k);
}

single Io {
    sync Void print(String s);
}

class Person {
    Int age;
    String name;
    List/String list_note;

    sync Void init(String name, Int age, List/String lst) {
        self.name = name;
        self.list_note = lst;
    }

    sync Void print_name() {
        void = Io.print(self.name);
    }
}

alias Map/String,Person to PersonMap;

class Org {
    PersonMap person_map;

    sync Void init(PersonMap person_map) {
        self.person_map = person_map;
    }

    async Void register_person(Person person) {
        void = self.person_map.put(person.name, person);
    }
}

flow create_person {
    String name!

    Int age!

    List/String lst!
    String sample_note!
    void = lst.add(sample_note);

    Person person!
    void = person.init(name, age, lst);


    Org org!
    PersonMap person_map!
    void = org.init(person_map); # sync call
    void << org.register_person(person); # async call


    Person person_2;
    person_2 = person;
}


// Document format

Comments: lines that start with hash.

Data structures

    Order declaration does not matter.

    Class

        Can be stubbed. Say /class Char./

        Can inherit from other classes. Write /class is parent,another/.

        Composes Objects, Synchronous Functions and Asynchronous Functions.

        You do not need to declare the body of functions.

    Generic

        Similar to class, but with substitution

    Alias

        Gives you shortcuts for referring to long class names. This is useful
        for giving short names to generics, in particular.

    Single

        A singleton. Think of this as a class that is immediately replaced by
        an object of the same name. Useful for templating factory objects.

    Void

        There is an automatic declaration of an empty type /Void/ and a
        corresponding global variable, /void/. This is a convenience.

Code blocks

    These are a list of statements. There are only a few types of valid
    statement.

    Declare an un-set variable

        String s.

    Declare a set variable

        String s!

    Synchronous copy

        s = person.name

    Synchronous invocation

        s = Factory.create_string()

    Asynchronous invocation

        s << Factory.create_string()

    Note

        note { content words }

        This form would become more useful if we do the work to generate
        sequence diagrams from Wandle notation.

    There is a built-in 'self' which refers to the scope that is enclosing the
    function. (This is similar to python use of /self/, or Java use of
    /this/.)

Flows

    Flows are asynchronous functions.
    
    Each should represent a use-case against the data model.

    Flows implicitly return Void.


// Closing notes

As of writing, when we parse an asynchronous statement, we should check that
we are inside an asynchronous context. It should be possible to add this.

Generics cannot inherit or be inherited. It would take work to implement this,
but it could be done.

At the time of writing, there is no way to declare objects at the global scope.



