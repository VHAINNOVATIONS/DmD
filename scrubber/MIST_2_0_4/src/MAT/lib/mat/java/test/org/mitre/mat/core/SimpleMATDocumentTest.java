package org.mitre.mat.core;

/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
import org.codehaus.jackson.node.JsonNodeFactory;
import org.codehaus.jackson.node.ArrayNode;
import org.codehaus.jackson.JsonNode;
import org.codehaus.jackson.JsonFactory;
import java.io.StringReader;
import org.codehaus.jackson.JsonParser;
import java.util.HashSet;
import java.util.HashMap;
import java.util.Set;
import java.util.LinkedHashSet;
import java.io.BufferedWriter;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.io.UnsupportedEncodingException;
import java.io.Writer;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import org.codehaus.jackson.map.ObjectMapper;
import org.junit.After;
import org.junit.AfterClass;
import org.junit.Before;
import org.junit.BeforeClass;
import org.junit.Test;
import static org.junit.Assert.*;

/**
 *
 * @author sam
 */
public class SimpleMATDocumentTest {

    public SimpleMATDocumentTest() {
    }

    @BeforeClass
    public static void setUpClass() throws Exception {
    }

    @AfterClass
    public static void tearDownClass() throws Exception {
    }

    @Before
    public void setUp() {
    }

    @After
    public void tearDown() {
    }
    private String DOC_TEXT = "Now is almost the time for all good men to come to the aid of their party.";

    // TODO add test methods here.
    // The methods must be annotated with annotation @Test. For example:
    //
    @Test
    public void testSignal() {
        MATDocument doc = new MATDocument();
        doc.setSignal(this.DOC_TEXT);
        assertTrue(doc.getSignal().equals(this.DOC_TEXT));
    }

    @Test
    public void testAtype() throws MATDocumentException, AnnotationException {
        MATDocument doc = new MATDocument();
        doc.setSignal(this.DOC_TEXT);
        Annotation a = doc.createAnnotation("ADVERB", 0, 3);
        assertTrue(doc.getDocRepository().size() == 1);
        Atype atype = doc.getDocRepository().get("ADVERB");
        assertTrue(atype != null);
        assertTrue(atype.getAttributes() != null);
        assertTrue(doc.findOrAddAtype("ADVERB") == atype);
        // Make sure it's still 1.
        assertTrue(doc.getDocRepository().size() == 1);
        doc.deleteAnnotation(a);
        assertTrue(doc.getAnnotationsOfType(atype).size() == 0);
        doc.addAnnotation(atype, a);
        assertTrue(doc.getAnnotationsOfType(atype).size() == 1);
        doc.deleteAnnotation(a);
        assertTrue(doc.getAnnotationsOfType(atype).size() == 0);
        doc.deleteAnnotation(a);
        assertTrue(doc.getAnnotationsOfType(atype).size() == 0);
    }

    @Test
    public void testTwoAtypes() throws MATDocumentException, AnnotationException {
        // I had a bug where JSON decoding was
        // reusing an array for the atype attributes.
        MATDocument doc = new MATDocument();
        doc.setSignal(this.DOC_TEXT);
        Annotation a = doc.createAnnotation("ADVERB", 0, 3);
        a.setAttributeValue("strength", "positive");
        Atype atype = doc.findOrAddAtype("ADPOSITION");
        Annotation b = doc.createAnnotation(atype, 7, 13);
        b.setAttributeValue("level", "high");
        MATJSONEncoding e = new MATJSONEncoding();
        String s = e.toEncodedString(doc);
        MATDocument doc2 = new MATDocument();
        e.fromEncodedString(doc2, s);
        assertTrue(doc2.getDocRepository().size() == 2);
        assertTrue(doc2.getDocRepository().get("ADVERB").getAttributes().size() == 1);
        assertTrue(doc2.getDocRepository().get("ADPOSITION").getAttributes().size() == 1);
        assertFalse(doc2.getDocRepository().get("ADVERB").getAttributes().get(0).equals(
                doc2.getDocRepository().get("ADPOSITION").getAttributes().get(0)));
    }

    @Test
    public void testAnnotation() throws MATDocumentException, AnnotationException {
        MATDocument doc = new MATDocument();
        doc.setSignal(this.DOC_TEXT);
        Annotation a = doc.createAnnotation("ADVERB", 0, 3);
        a.setAttributeValue("strength", "positive");
        Atype atype = doc.findOrAddAtype("ADVERB");
        assertTrue(doc.getAnnotationsOfType(atype).size() == 1);
        Annotation b = doc.createAnnotation(atype, 7, 13);
        b.setAttributeValue("level", "high");
        assertTrue(doc.getAnnotationsOfType(atype).size() == 2);
        assertTrue(atype.getAttributes().size() == 2);
        assertTrue(atype.getAttributes().get(0).getName().equals("strength"));
        assertTrue(atype.getAttributes().get(1).getName().equals("level"));
        assertTrue(a.getAttributeValue("strength").equals("positive"));
        assertTrue(b.getAttributeValue("strength") == null);
        assertTrue(a.getAttributeValue("level") == null);
        assertTrue(b.getAttributeValue("level").equals("high"));
    }

    @Test
    public void testEncodeDecode() throws MATDocumentException, AnnotationException {
        MATDocument doc = new MATDocument();
        doc.setSignal(this.DOC_TEXT);
        Annotation a = doc.createAnnotation("ADVERB", 0, 3);
        a.setAttributeValue("strength", "positive");
        Atype atype = doc.findOrAddAtype("ADVERB");
        Annotation b = doc.createAnnotation(atype, 7, 13);
        b.setAttributeValue("level", "high");
        assertTrue(doc.getAnnotationsOfType(atype).size() == 2);
        assertTrue(doc.getAnnotationsOfType(atype).size() == 2);
        MATJSONEncoding e = new MATJSONEncoding();
        String s = e.toEncodedString(doc);
        System.out.println(s);
        MATDocument doc2 = new MATDocument();
        e.fromEncodedString(doc2, s);
        assertTrue(doc2.getDocRepository().size() == 1);
        atype = doc2.getDocRepository().get("ADVERB");
        assertTrue(atype != null);
        assertTrue(doc2.getAnnotationsOfType(atype).size() == 2);
        assertTrue(atype.getAttributes().size() == 2);
        assertTrue(atype.getAttributes().get(0).getName().equals("strength"));
        assertTrue(atype.getAttributes().get(1).getName().equals("level"));
        a = (Annotation) doc2.getAnnotationsOfType(atype).get(0);
        b = (Annotation) doc2.getAnnotationsOfType(atype).get(1);
        if (a.getStartIndex() == 7) {
            Annotation temp = b;
            b = a;
            a = temp;
        }
        assertTrue(a.getAttributeValue("strength").equals("positive"));
        assertTrue(b.getAttributeValue("strength") == null);
        assertTrue(a.getAttributeValue("level") == null);
        assertTrue(b.getAttributeValue("level").equals("high"));
    }

    // More tests for spanless annotations, and annotation-valued
    // attributes. Copied essentially directly from Python.
    @Test
    public void testID() throws MATDocumentException, AnnotationException {
        MATDocument doc = new MATDocument();
        doc.setSignal("This is a test document.");
        Annotation newAnnot = doc.createAnnotation("NOUN", 0, 4);
        String id = newAnnot.getID();
        assertTrue(newAnnot == doc.getAnnotationByID(id));
        // Remove it.
        doc.deleteAnnotation(newAnnot);
        assertTrue(doc.getAnnotationByID(id) == null);
    }

    @Test
    public void testManyIDs() throws MATDocumentException, AnnotationException {
        MATDocument doc = new MATDocument();
        doc.setSignal("This is a test document.");
        Annotation a1 = doc.createAnnotation("NOUN", 0, 4);
        Annotation a2 = doc.createAnnotation("VERB", 5, 7);
        String id1 = a1.getID();
        String id2 = a2.getID();
        // Remove
        doc.deleteAnnotations(Arrays.asList((AnnotationCore) a1));
        assertTrue(doc.getAnnotationByID(id1) == null);
        assertTrue(doc.getAnnotationByID(id2) == a2);
        // No reusing IDs.
        Annotation a3 = doc.createAnnotation("NOUN", 0, 4);
        String id3 = a3.getID();
        assertTrue(!id1.equals(id3));
        doc.deleteAnnotations(Arrays.asList((AnnotationCore) a2));
        assertTrue(doc.getAnnotationByID(id2) == null);
        // Now, remove them all.
        doc.deleteAllAnnotations();
        // NOW there's reuse.
        Annotation a4 = doc.createAnnotation("NOUN", 0, 4);
        String id4 = a4.getID();
        assertTrue(id1.equals(id4));

    }

    @Test
    public void testIDSerialization() throws MATDocumentException, AnnotationException {
        MATDocument doc = new MATDocument();
        doc.setSignal("This is a test document.");
        Annotation a1 = doc.createAnnotation("NOUN", 0, 4);
        a1.setAttributeValue("number", "plural");
        String id1 = a1.getID();
        Annotation a2 = doc.createAnnotation("VERB", 5, 7);
        a2.setAttributeValue("number", "singular");

        // Now, check the dictionary.
        MATJSONEncoding e = new MATJSONEncoding();
        Map m = e.toJsonNode(doc);

        Iterator it = ((List) m.get("asets")).iterator();
        while (it.hasNext()) {
            Map t = (Map) it.next();
            if ("NOUN".equals((String) t.get("type"))) {
                assertTrue((Boolean) t.get("hasID"));
                // The noun should have annots of length 4, the verbs of length 3.
                assertTrue(((List) ((List) t.get("annots")).get(0)).size() == 4);
                break;
            }
        }
        it = ((List) m.get("asets")).iterator();
        while (it.hasNext()) {
            Map t = (Map) it.next();
            if ("VERB".equals((String) t.get("type"))) {
                assertTrue(!(Boolean) t.get("hasID"));
                assertTrue(((List) ((List) t.get("annots")).get(0)).size() == 3);
                break;
            }
        }

        // Now, check the actual serialization.
        MATDocument newDoc = new MATDocument();
        e.fromEncodedString(newDoc, e.toEncodedString(doc));
        // Make sure the ID is preserved.
        assertTrue(newDoc.getAnnotationsOfType("NOUN").get(0).getID(false).equals(id1));
        assertTrue(newDoc.getAnnotationsOfType("VERB").get(0).getID(false) == null);
        assertTrue(newDoc.getAnnotationByID(id1) == newDoc.getAnnotationsOfType("NOUN").get(0));
        // Make sure the features are decoded correctly.
        assertTrue(newDoc.getAnnotationsOfType("NOUN").get(0).getAttributeValue("number").equals("plural"));
        assertTrue(newDoc.getAnnotationsOfType("VERB").get(0).getAttributeValue("number").equals("singular"));
    }

    @Test
    public void testVersion1SerializationDefaults() throws MATDocumentException, UnsupportedEncodingException, IOException, AnnotationException {
        // Let's create a document, render the dictionary, surgically
        // alter it, and then dump it and read it back.

        MATDocument doc = new MATDocument();
        doc.setSignal("This is a test document.");
        Annotation a1 = doc.createAnnotation("NOUN", 0, 4);
        a1.setAttributeValue("number", "plural");
        Annotation a2 = doc.createAnnotation("VERB", 5, 7);
        a2.setAttributeValue("number", "singular");

        MATJSONEncoding e = new MATJSONEncoding();
        Map m = e.toJsonNode(doc);

        m.put("version", 1);
        Iterator it = ((List) m.get("asets")).iterator();
        while (it.hasNext()) {
            Map atype = (Map) it.next();
            if (atype.containsKey("hasSpan")) {
                atype.remove("hasSpan");
            }
            if (atype.containsKey("hasID")) {
                atype.remove("hasID");
            }
            Iterator it2 = ((List) atype.get("attrs")).iterator();
            ArrayList<String> names = new ArrayList<String>();
            while (it2.hasNext()) {
                names.add((String) ((Map) it2.next()).get("name"));
            }
            atype.put("attrs", names);
        }
        MATDocument doc2 = new MATDocument();

        // This next block is required to write the
        // damn JSON map. Ugh.
        Writer exportWriter = null;
        ObjectMapper mapper = new ObjectMapper();
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        exportWriter = new OutputStreamWriter(b, "UTF-8");
        exportWriter = new BufferedWriter(exportWriter);
        mapper.writeValue(exportWriter, m);
        exportWriter.close();

        e.fromEncodedString(doc2, b.toString("UTF-8"));

        Iterator<Atype> it2 = doc2.docRepository.values().iterator();

        while (it2.hasNext()) {
            Atype a = it2.next();
            assertTrue(a.getHasSpan());
            assertTrue(!a.hasAnnotationAttribute());
        }

    }

    @Test
    public void testBadAnnotationValuedIDs() throws MATDocumentException, AnnotationException {

        MATDocument doc = new MATDocument();
        doc.setSignal("This is a test document.");
        Annotation a1 = doc.createAnnotation("NOUN", 0, 4);
        Annotation a2 = doc.createAnnotation("VERB", 5, 7);
        a2.setAttributeValue("number", "singular");

        // We didn't declare this as annotation-valued, but
        // it will be automatically declared.
        a2.setAttributeValue("subject", a1);

        // Now if we try to reset it, it won't work.
        try {
            a2.setAttributeValue("subject", "mysubj");
            fail("attribute setting should have failed");
        } catch (MATDocumentException e) {
            assertTrue(e.toString().indexOf("types don't match") > -1);
        }
        try {
            a2.parentAtype.findOrAddAttribute("subj", "annotation");
        } catch (AnnotationException ex) {
            fail("findOrAddAttribute should have succeeded");
        }
        try {
            a2.setAttributeValue("subj", "noun");
            fail("attribute setting should have failed");
        } catch (MATDocumentException e) {
            assertTrue(e.toString().indexOf("types don't match") > -1);
        }

        try {
            a2.setAttributeValue("number", a1);
            fail("attribute setting should have failed");
        } catch (MATDocumentException e) {
            assertTrue(e.toString().indexOf("types don't match") > -1);
        }
    }

    @Test
    public void testAnnotationValuedIDs() throws MATDocumentException, AnnotationException {

        MATDocument doc = new MATDocument();
        doc.setSignal("This is a test document.");
        Annotation a1 = doc.createAnnotation("NOUN", 0, 4);
        Annotation a2 = doc.createAnnotation("VERB", 5, 7);
        a2.setAttributeValue("number", "singular");

        a2.setAttributeValue("subj", a1);
        assertTrue(a1.getID(false) != null);

        String id = a1.getID();

        // Serialize, deserialize.
        MATJSONEncoding e = new MATJSONEncoding();
        String s = e.toEncodedString(doc);
        System.out.println(s);
        MATDocument newDoc = new MATDocument();
        e.fromEncodedString(newDoc, s);

        // Make sure the ID is preserved.
        assertTrue(newDoc.getAnnotationsOfType("NOUN").get(0).getID(false).equals(id));
        assertTrue(newDoc.getAnnotationsOfType("VERB").get(0).getID(false) == null);
        AnnotationCore vA = newDoc.getAnnotationsOfType("VERB").get(0);
        assertTrue(vA.getAttributeValues().size() == 2);
        assertTrue(vA.getAttributeValues().get(0).equals("singular"));
        assertTrue(vA.getAttributeValues().get(1) == newDoc.getAnnotationsOfType("NOUN").get(0));
    }

    @Test
    public void testAnnotationDeletion() throws MATDocumentException, AnnotationException {

        MATDocument doc = new MATDocument();
        doc.setSignal("This is a test document.");
        Annotation a1 = doc.createAnnotation("NOUN", 0, 4);
        Annotation a2 = doc.createAnnotation("VERB", 5, 7);
        a2.setAttributeValue("number", "singular");

        a2.setAttributeValue("subj", a1);
        // You shouldn't be able to delete an annotation that someone
        // points to.
        try {
            doc.deleteAnnotations(Arrays.asList((AnnotationCore) a1));
            fail("annotation removal should have failed");
        } catch (MATDocumentException e) {
            assertTrue(e.toString().indexOf("can't be pointed to by annotations outside the group") > -1);
        }

        // But you SHOULD be able to delete an annotation that points
        // to it.
        doc.deleteAnnotations(Arrays.asList((AnnotationCore) a2));
        // And there should be no trace of a2 pointing to anything.
        doc.deleteAnnotations(Arrays.asList((AnnotationCore) a1));

        // Ugh. Overwriting also has to work. But what if you have two references
        // to the same annot, but you only overwrite one? AAAARGH. Fixed that.
        // Rebuild it.
        a1 = doc.createAnnotation("NOUN", 0, 4);
        a2 = doc.createAnnotation("VERB", 5, 7);
        a2.setAttributeValue("number", "singular");
        a2.setAttributeValue("subj", a1);

        Annotation a3 = doc.createAnnotation("NOUN", 15, 23);
        a2.setAttributeValue("obj", a3);
        a2.setAttributeValue("dobj", a1);
        // Now, if I overwrite the subject, I should fail to be
        // able to remove a1, because it's pointing to multiple
        // things.
        a2.setAttributeValue("subj", a3);
        try {
            doc.deleteAnnotation(a1);
            fail("annotation removal should have failed");
        } catch (MATDocumentException e) {
            assertTrue(e.toString().indexOf("can't be pointed to by annotations outside the group") > -1);
        }

        // Now, I set dobj to None. If I've done the bookkeeping
        // correctly, this should now allow me to delete a1, but I think
        // there's a bug I need to fix which will cause this to fail.
        // We have to cast this, because the method reference is ambiguous.
        a2.setAttributeValue("dobj", (AnnotationCore) null);
        doc.deleteAnnotation(a1);
        // But not a3.
        try {
            doc.deleteAnnotation(a3);
            fail("annotation removal should have failed");
        } catch (MATDocumentException e) {
            assertTrue(e.toString().indexOf("can't be pointed to by annotations outside the group") > -1);
        }

        // Now, let's make them point to each other.
        a3.setAttributeValue("subj_of", a2);
        // So now, we can't remove a2 either.
        try {
            doc.deleteAnnotation(a2);
            fail("annotation removal should have failed");
        } catch (MATDocumentException e) {
            assertTrue(e.toString().indexOf("can't be pointed to by annotations outside the group") > -1);
        }
        // But you should be able to remove the two of them together.
        doc.deleteAnnotations(Arrays.asList((AnnotationCore) a2, (AnnotationCore) a3));

    }

    private MATDocument createSpanlessDoc() throws MATDocumentException, AnnotationException {

        MATDocument doc = new MATDocument();
        doc.setSignal("This is a test document.");
        Annotation a1 = doc.createAnnotation("NOUN", 0, 4);
        Annotation a2 = doc.createAnnotation("VERB", 5, 7);
        a2.setAttributeValue("number", "singular");
        Annotation a3 = doc.createAnnotation("NOUN", 15, 23);
        Atype fType = doc.findOrAddAtype("FRAME", false);
        SpanlessAnnotation a4 = doc.createSpanlessAnnotation("FRAME");
        a4.setAttributeValue("subj", a1);
        a4.setAttributeValue("verb", a2);
        a4.setAttributeValue("obj", a3);
        a4.setAttributeValue("telic", "no");
        return doc;
    }

    @Test
    public void testSpanlessRendering() throws MATDocumentException, AnnotationException {
        MATDocument d = this.createSpanlessDoc();
        MATJSONEncoding e = new MATJSONEncoding();
        e.toJsonNode(d);
    }

    @Test
    public void testBasicSpanless() throws MATDocumentException, AnnotationException {
        MATDocument d = this.createSpanlessDoc();
        // Shouldn't be able to delete only partial set.
        try {
            d.deleteAnnotations(d.getAnnotationsOfType("VERB"));
            fail("annotation removal should have failed");
        } catch (MATDocumentException e) {
            assertTrue(e.toString().indexOf("can't be pointed to by annotations outside the group") > -1);
        }
        // But yes to the frame.
        d.deleteAnnotations(d.getAnnotationsOfType("FRAME"));
        // And then, yes to the verb.
        d.deleteAnnotations(d.getAnnotationsOfType("VERB"));
    }

    @Test
    public void testJSONSerialization() throws MATDocumentException, AnnotationException {
        MATDocument doc = this.createSpanlessDoc();

        // Serialize, deserialize.
        MATJSONEncoding e = new MATJSONEncoding();
        String s = e.toEncodedString(doc);
        // System.out.println(s);
        MATDocument newDoc = new MATDocument();
        e.fromEncodedString(newDoc, s);
        assertTrue(!newDoc.findAtypeOfType("FRAME").getHasSpan());

        // I don't have orderAnnotations in the Java bindings, so
        // in order to check the noun and verb IDs, I'm going to have
        // to do something different.
        Iterator<AnnotationCore> it = newDoc.getAnnotationsOfType("NOUN").iterator();
        while (it.hasNext()) {
            AnnotationCore a = it.next();
            assertTrue(a.getID(false).equals(doc.getAnnotationByID(a.getID(false)).getID(false)));
        }
        it = newDoc.getAnnotationsOfType("VERB").iterator();
        while (it.hasNext()) {
            AnnotationCore a = it.next();
            assertTrue(a.getID(false).equals(doc.getAnnotationByID(a.getID(false)).getID(false)));
        }

        assertTrue(newDoc.findAtypeOfType("NOUN").getHasSpan());
        assertTrue(newDoc.findAtypeOfType("VERB").getHasSpan());
        assertTrue(((AnnotationCore) doc.getAnnotationsOfType("FRAME").get(0).getAttributeValue("subj")).getID(false).equals(
                ((AnnotationCore) doc.getAnnotationsOfType("FRAME").get(0).getAttributeValue("subj")).getID(false)));
        assertTrue(((AnnotationCore) doc.getAnnotationsOfType("FRAME").get(0).getAttributeValue("obj")).getID(false).equals(
                ((AnnotationCore) doc.getAnnotationsOfType("FRAME").get(0).getAttributeValue("obj")).getID(false)));
        assertTrue(((AnnotationCore) doc.getAnnotationsOfType("FRAME").get(0).getAttributeValue("verb")).getID(false).equals(
                ((AnnotationCore) doc.getAnnotationsOfType("FRAME").get(0).getAttributeValue("verb")).getID(false)));
        assertTrue(doc.getAnnotationsOfType("FRAME").get(0).getAttributeValue("telic").equals("no"));

    }

    @Test
    public void testAnnotationAttributeSetDelete() throws MATDocumentException, AnnotationException {
        MATDocument doc = new MATDocument();
        doc.setSignal("This is a test document.");
        Annotation a1 = doc.createAnnotation("NOUN", 0, 4);
        List a1list = Arrays.asList(new AnnotationCore[]{a1});
        Annotation a2 = doc.createAnnotation("VERB", 5, 7);
        List a2list = Arrays.asList(new AnnotationCore[]{a2});
        a2.setAttributeValue("number", "singular");
        a2.getParentAtype().findOrAddAttribute("subj", Atype.ANNOTATION_ATTR_TYPE, AttributeType.SET_AGGREGATION);
        a2.setAttributeValue("subj", Atype.ANNOTATION_ATTR_TYPE,
                new AttributeValueSet(new LinkedHashSet(a1list)));
        // you should not be able to delete an annotation that someone points to
        try {
            doc.deleteAnnotations(a1list);
            fail("annotation removal should have failed");
        } catch (MATDocumentException e) {
            assertTrue(e.getMessage().contains("can't be pointed to by annotations outside the group"));
        }
        // but you SHOULD be able to delete an annotation that point to something
        doc.deleteAnnotations(a2list);
        // and there should remain no trace of a2 pointing to anything
        doc.deleteAnnotations(a1list);
        // rebuild it
        a1 = doc.createAnnotation("NOUN", 0, 4);
        a1list = Arrays.asList(new AnnotationCore[]{a1});
        a2 = doc.createAnnotation("VERB", 5, 7);
        a2.setAttributeValue("number", "singular");
        a2.setAttributeValue("subj", Atype.ANNOTATION_ATTR_TYPE,
                new AttributeValueSet(new LinkedHashSet(a1list)));

        Annotation a3 = doc.createAnnotation("NOUN", 15, 23);
        a2.getParentAtype().findOrAddAttribute("obj", Atype.ANNOTATION_ATTR_TYPE);
        a2.setAttributeValue("obj", a3);
        a2.getParentAtype().findOrAddAttribute("dobj", Atype.ANNOTATION_ATTR_TYPE);
        a2.setAttributeValue("dobj", a1);

        // now if I remove the subject, I should fail to be able to remove a1 
        // because it's pointing to multiple things (pointed to by multiple things?)
        ((AttributeValueSet) a2.getAttributeValue("subj")).remove(a1);
        try {
            doc.deleteAnnotation(a1);
            fail("annotation removal should have failed");
        } catch (MATDocumentException e) {
            assertTrue(e.getMessage().contains("can't be pointed to by annotations outside the group"));
        }

        // now clear dobj -- if we've doine the bookkeeping correctly, this
        // should allow us to delete a1
        a2.setAttributeValue("dobj", (AnnotationCore) null); // gross that we have to cast null here to know which version of setAttributeValue to use

        // And add it back.  this is a sort of possible error (?)  Let's raise
        // an error if an annotation value isn't in the document.  Or maybe
        // we need to rethink this whole thing of needing to add the annotation
        doc.addAnnotation(a1.getParentAtype(), a1);

        ((AttributeValueSet) a2.getAttributeValue("subj")).add(a1);

        // now let's make them point to each other
        a1.getParentAtype().findOrAddAttribute("subj_of", Atype.ANNOTATION_ATTR_TYPE);
        a1.setAttributeValue("subj_of", a2);

        // so now we should be able to remove a2 either
        try {
            doc.deleteAnnotation(a2);
            fail("annotation removal should have failed");
        } catch (MATDocumentException e) {
            assertTrue(e.getMessage().contains("can't be pointed to by annotations outside the group"));
        }

        // but we should be able to remove the two of them together
        List a12list = Arrays.asList(new AnnotationCore[]{a1, a2});
        doc.deleteAnnotations(a12list);

    }
    // here we start a new class in the python, but I'm just ramming everything together here
    MATDocument theDoc;
    Map<String, List<Object>> POSSIBLE_TEST_VALUES = new HashMap<String, List<Object>>();

    @Test
    public void testAttrTypes() throws MATDocumentException, AnnotationException {
        setUpAttrTest();
        for (Iterator i = POSSIBLE_TEST_VALUES.keySet().iterator(); i.hasNext();) {
            String attrtype = (String) i.next();
            System.out.println("doing testAttrType for " + attrtype);
            testAttributeType(attrtype);
            System.out.println("done testAttrType for " + attrtype);
        }
    }

    private void setUpAttrTest() throws MATDocumentException, AnnotationException {
        theDoc = new MATDocument();
        theDoc.setSignal("This is a test document");
        Atype ftype = theDoc.findOrAddAtype("AttrTest");
        Annotation a1 = theDoc.createAnnotation(ftype, 0, 4);
        POSSIBLE_TEST_VALUES.put(Atype.STRING_ATTR_TYPE, Arrays.asList(new Object[]{"abc", "def"}));
        POSSIBLE_TEST_VALUES.put(Atype.INT_ATTR_TYPE, Arrays.asList(new Object[]{new Integer(5)}));
        POSSIBLE_TEST_VALUES.put(Atype.FLOAT_ATTR_TYPE, Arrays.asList(new Object[]{new Float(5.3)}));
        POSSIBLE_TEST_VALUES.put(Atype.ANNOTATION_ATTR_TYPE, Arrays.asList(new Object[]{a1}));
        POSSIBLE_TEST_VALUES.put(Atype.BOOLEAN_ATTR_TYPE, Arrays.asList(new Object[]{true}));
    }

    private void testAttributeType(String attrtype) throws MATDocumentException, AnnotationException {
        MATDocument doc = theDoc;
        String kAttr = attrtype + "Attr";
        List<Object> vals = POSSIBLE_TEST_VALUES.get(attrtype);
        Atype ftype = doc.findAtypeOfType("AttrTest");
        ftype.findOrAddAttribute(kAttr, attrtype);
        doc.createAnnotation(ftype, 0, 4);
        HashMap valsMap = new HashMap();
        for (Iterator i = vals.iterator(); i.hasNext();) {
            Object nextval = i.next();
            valsMap.put(kAttr, nextval);
            doc.createAnnotation(ftype, 0, 4, valsMap);
        }
        Set<String> keys = POSSIBLE_TEST_VALUES.keySet();
        Set allOtherVals = new HashSet();
        for (Iterator<String> i = keys.iterator(); i.hasNext();) {
            String k = i.next();
            if (!k.equals(attrtype)) {
                allOtherVals.addAll(POSSIBLE_TEST_VALUES.get(k));
            }
        }
        for (Iterator i = allOtherVals.iterator(); i.hasNext();) {
            Object nextval = i.next();
            valsMap.put(kAttr, nextval);
            try {
                doc.createAnnotation(ftype, 0, 4, valsMap);
                fail("annotation creation should have failed");
            } catch (AnnotationException e) {
                assertTrue(e.getMessage().contains("must be a"));
            } catch (MATDocumentException e) {
                assertTrue(e.getMessage().contains("types don't match"));
            }
            Annotation a2 = doc.createAnnotation("AttrTest", 0, 4);
            // in each type-specific test, in addition to this, we should do one where
            // a typed value is passed in to setAttributeValue
            try {
                a2.setAttributeValue(kAttr, nextval);
                fail("attribute setting should have failed");
//            } catch (AnnotationException e) { 
//               assertTrue(e.getMessage().contains("must be a"));
            } catch (MATDocumentException e) {
                assertTrue(e.getMessage().contains("types don't match"));
            }
        }
        testListAttribute(attrtype, allOtherVals, ftype);
        testSetAttribute(attrtype, allOtherVals, ftype);
    }

    private void testListAttribute(String attrtype, Set allOtherVals, Atype ftype) throws AnnotationException, MATDocumentException {
        System.out.println("doing testListAttribute for " + attrtype);
        MATDocument doc = theDoc;
        String kAttr = attrtype + "ListAttr";
        // do good values
        List<Object> goodVals = POSSIBLE_TEST_VALUES.get(attrtype);
        AttributeValueList goodAttrValsList = new AttributeValueList(goodVals);
        Map mapOfAttrVals = new HashMap();
        mapOfAttrVals.put(kAttr, goodAttrValsList);
        ftype.findOrAddAttribute(kAttr, attrtype, AttributeType.LIST_AGGREGATION);
        doc.createAnnotation("AttrTest", 0, 4);
        Annotation a1 = doc.createAnnotation("AttrTest", 0, 4, mapOfAttrVals);
        a1.setAttributeValue(kAttr, attrtype, goodAttrValsList);

        // check serialize/deserialize of an attribute with a list value
        String id = a1.getID();
        MATJSONEncoding enc = new MATJSONEncoding();
        String s = enc.toEncodedString(doc);
        System.out.println(s);
        MATDocument newDoc = new MATDocument();
        enc.fromEncodedString(newDoc, s);

        AttributeValueList avlist = (AttributeValueList) newDoc.getAnnotationByID(id).getAttributeValue(kAttr);
        if (!Atype.ANNOTATION_ATTR_TYPE.equals(attrtype)) { // ugh, not sure what I can assert for annotations as the annots in the lists won't be "equal" even when the same
            assertTrue(avlist.collectionEquals(goodAttrValsList));
        }

        // now bad values
        ArrayList otherNumbers = new ArrayList();
        for (Iterator i = allOtherVals.iterator(); i.hasNext();) {
            Object nextval = i.next();
            if (Atype.FLOAT_ATTR_TYPE.equals(attrtype) && (nextval instanceof Number)) {
                // that's not really a badVal; add it to otherNumbers and try them at the end
                otherNumbers.add(nextval);
                continue;
            }

            List nextValAsList = Arrays.asList(new Object[]{nextval});
            AttributeValueList attrValList = new AttributeValueList(nextValAsList);
            Map nextMapOfAttrVals = new HashMap();
            nextMapOfAttrVals.put(kAttr, attrValList);
            try {
                doc.createAnnotation(ftype, 0, 4, nextMapOfAttrVals);
                fail("annotation creation should have failed");

            } catch (AnnotationException e) {
                assertTrue(e.getMessage().contains("must be a"));
            }
            Annotation a2 = doc.createAnnotation("AttrTest", 0, 4);
            try {
                a2.setAttributeValue(kAttr, attrtype, attrValList);
                fail("attribute set should have failed");
            } catch (AnnotationException e) {
                assertTrue(e.getMessage().contains("must be a"));
            }
            try {
                ((AttributeValueList) a1.getAttributeValue(kAttr)).add(nextval);
                fail("attribute add should have failed");
            } catch (AnnotationException e) {
                assertTrue(e.getMessage().contains("must be a"));
            }
            try {
                ((AttributeValueList) a1.getAttributeValue(kAttr)).addAll(nextValAsList);
                fail("attribute add should have failed");
            } catch (AnnotationException e) {
                assertTrue(e.getMessage().contains("must be a"));
            }
            // this should be ok until we try to set it
            ArrayList mixedList = new ArrayList(goodVals);
            mixedList.add(nextval);
            AttributeValueList b = new AttributeValueList(mixedList);
            try {
                a2.setAttributeValue(kAttr, attrtype, b);
                fail("mixed attribute list set should have failed");
            } catch (AnnotationException e) {
                assertTrue(e.getMessage().contains("must be a"));
            }
        }
        if (Atype.FLOAT_ATTR_TYPE.equals(attrtype)) {
            Annotation a3 = doc.createAnnotation("AttrTest", 0, 4, mapOfAttrVals);
            a3.setAttributeValue(kAttr, attrtype, new AttributeValueList(otherNumbers));
        }
        try {
            Map mapOfSetAttrVals = new HashMap();
            mapOfSetAttrVals.put(kAttr, new AttributeValueSet(new HashSet(goodVals)));
            doc.createAnnotation("AttrTest", 0, 4, mapOfSetAttrVals);
            fail("annotation creation should have failed");
        } catch (AnnotationException e) {
            assertTrue(e.getMessage().contains("must be a"));
        } catch (MATDocumentException e) {
            assertTrue(e.getMessage().contains("types don't match"));
        }

    }

    private void testSetAttribute(String attrtype, Set allOtherVals, Atype ftype) throws AnnotationException, MATDocumentException {
        System.out.println("doing testSetAttribute for " + attrtype);
        MATDocument doc = theDoc;
        String kAttr = attrtype + "SetAttr";
        // do good values
        Set<Object> goodVals = new HashSet(POSSIBLE_TEST_VALUES.get(attrtype));
        AttributeValueSet goodAttrValSet = new AttributeValueSet(goodVals);
        Map mapOfAttrVals = new HashMap();
        mapOfAttrVals.put(kAttr, goodAttrValSet);
        ftype.findOrAddAttribute(kAttr, attrtype, AttributeType.SET_AGGREGATION);
        doc.createAnnotation("AttrTest", 0, 4);
        Annotation a1 = doc.createAnnotation("AttrTest", 0, 4, mapOfAttrVals);
        a1.setAttributeValue(kAttr, attrtype, goodAttrValSet);

        // check serialize/deserialize of an attribute with a set value
        String id = a1.getID();
        MATJSONEncoding enc = new MATJSONEncoding();
        String s = enc.toEncodedString(doc);
        System.out.println(s);
        MATDocument newDoc = new MATDocument();
        enc.fromEncodedString(newDoc, s);

        AttributeValueSet avset = (AttributeValueSet) newDoc.getAnnotationByID(id).getAttributeValue(kAttr);
        if (!Atype.ANNOTATION_ATTR_TYPE.equals(attrtype)) { // ugh, not sure what I can assert for annotations as the lists won't be "equal" even when the same
            assertTrue(avset.collectionEquals(goodAttrValSet));
        }

        // now bad values
        Set otherNumbers = new HashSet();
        for (Iterator i = allOtherVals.iterator(); i.hasNext();) {
            Object nextval = i.next();
            if (Atype.FLOAT_ATTR_TYPE.equals(attrtype) && (nextval instanceof Number)) {
                // that's not really a badVal; add it to otherNumbers and try them at the end
                otherNumbers.add(nextval);
                continue;
            }
            Set nextValAsSet = new HashSet(Arrays.asList(new Object[]{nextval}));
            AttributeValueSet attrValSet = new AttributeValueSet(nextValAsSet);
            Map nextMapOfAttrVals = new HashMap();
            nextMapOfAttrVals.put(kAttr, attrValSet);
            try {
                doc.createAnnotation(ftype, 0, 4, nextMapOfAttrVals);
                fail("annotation creation should have failed");
            } catch (AnnotationException e) {
                assertTrue(e.getMessage().contains("must be a"));
            }
            Annotation a2 = doc.createAnnotation("AttrTest", 0, 4);
            try {
                a2.setAttributeValue(kAttr, attrtype, attrValSet);
                fail("attribute set should have failed");
            } catch (AnnotationException e) {
                assertTrue(e.getMessage().contains("must be a"));
            }
            try {
                // using a1 here because it will not return null from getAttributeValue, whereas a2 will
                ((AttributeValueSet) a1.getAttributeValue(kAttr)).add(nextval);
                fail("attribute add should have failed");
            } catch (AnnotationException e) {
                assertTrue(e.getMessage().contains("must be a"));
            }
            try {
                ((AttributeValueSet) a1.getAttributeValue(kAttr)).addAll(nextValAsSet);
                fail("attribute add should have failed");
            } catch (AnnotationException e) {
                assertTrue(e.getMessage().contains("must be a"));
            }
            // this should be ok until we try to set it
            Set mixedSet = new HashSet(goodVals);
            mixedSet.add(nextval);
            AttributeValueSet b = new AttributeValueSet(mixedSet);
            try {
                a2.setAttributeValue(kAttr, attrtype, b);
                fail("mixed attribute Set set should have failed");
            } catch (AnnotationException e) {
                assertTrue(e.getMessage().contains("must be a"));
            } catch (MATDocumentException e) {
                assertTrue(e.getMessage().contains("types don't match"));
            }
        }
        if (Atype.FLOAT_ATTR_TYPE.equals(attrtype)) {
            Annotation a3 = doc.createAnnotation("AttrTest", 0, 4, mapOfAttrVals);
            a3.setAttributeValue(kAttr, attrtype, new AttributeValueSet(otherNumbers));
        }
        try {
            Map mapOfListAttrVals = new HashMap();
            mapOfListAttrVals.put(kAttr, new AttributeValueList(new ArrayList(goodVals)));
            doc.createAnnotation("AttrTest", 0, 4, mapOfListAttrVals);
            fail("annotation creation should have failed");
        } catch (AnnotationException e) {
            assertTrue(e.getMessage().contains("must be a"));
        } catch (MATDocumentException e) {
            assertTrue(e.getMessage().contains("types don't match"));
        }
        // check serialize/deserialize
    }

    @Test
    public void testStringExtended() throws MATDocumentException, AnnotationException {
        MATDocument doc = new MATDocument();
        doc.setSignal("This is a test document.");
        Atype ftype = doc.findOrAddAtype("AttrTest");
        Annotation a1 = doc.createAnnotation(ftype, 0, 4);
        // test invalid restrictions
        Map restMap = new HashMap();
        List badChoices = Arrays.asList(new Object[]{"a", new Integer(5)});
        restMap.put("choices", badChoices);
        tryBadRestrictions("string_badchoices", ftype, restMap);
        // setup valid choice restrictions
        restMap.clear();
        List goodChoices = Arrays.asList(new String[]{"a", "bcd", "e"});
        restMap.put("choices", goodChoices);
        int theAttrIndex = ftype.findOrAddAttribute("t_string_choices2", Atype.STRING_ATTR_TYPE, AttributeType.NONE_AGGREGATION, restMap);
        // try a good value
        Map goodValHash = new HashMap();
        a1.setAttributeValue("t_string_choices2", "a");
        goodValHash.put("t_string_choices2", "a");
        // try a bad value
        try {
            a1.setAttributeValue("t_string_choices2", "b");
            fail("attr set should have failed");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("must be a"));
        }
        testJsonIO(doc, a1, goodValHash, Atype.STRING_ATTR_TYPE);
    }

    @Test
    public void testIntExtended() throws MATDocumentException, AnnotationException {
        MATDocument doc = new MATDocument();
        doc.setSignal("This is a test document.");
        Atype ftype = doc.findOrAddAtype("AttrTest");
        Annotation a1 = doc.createAnnotation(ftype, 0, 4);
        Map goodValMap = new HashMap();

        // test invalid restrictions
        Map restMap = new HashMap();
        List badChoices = Arrays.asList(new Object[]{new Integer(5), new Integer(6), "b"});
        restMap.put("choices", badChoices);
        tryBadRestrictions("int_badchoices", ftype, restMap);
        restMap.clear();
        restMap.put("minval", Boolean.TRUE);
        tryBadRestrictions("int_badminval", ftype, restMap);
        restMap.clear();
        restMap.put("maxval", "7");
        tryBadRestrictions("int_badmaxval", ftype, restMap);

        // setup valid choice restrictions
        // TODO deal with Longs?
        restMap.clear();
        List goodChoices = Arrays.asList(new Integer[]{5, 6, 20});
        restMap.put("choices", goodChoices);
        this.testRestriction(a1, "int_goodchoices", restMap, ftype, Atype.INT_ATTR_TYPE, goodValMap,
                Arrays.asList(new Integer[]{6, 5}),
                Arrays.asList(new Integer[]{8}));

        // setup valid minval restriction
        restMap.clear();
        restMap.put("minval", new Integer(11));
        this.testRestriction(a1, "int_goodminval", restMap, ftype, Atype.INT_ATTR_TYPE, goodValMap,
                Arrays.asList(new Integer[]{12, 11}),
                Arrays.asList(new Integer[]{10}));

        // setup valid maxval restriction
        restMap.clear();
        restMap.put("maxval", new Integer(20));
        this.testRestriction(a1, "int_goodmaxval", restMap, ftype, Atype.INT_ATTR_TYPE, goodValMap,
                Arrays.asList(new Integer[]{15, 20}),
                Arrays.asList(new Integer[]{33}));

        // setup valid minval and choices -- this should now fail
        restMap.clear();
        restMap.put("choices", goodChoices);
        restMap.put("minval", new Integer(10));
        /***
        this.testRestriction(a1, "int_goodminandchoices", restMap, ftype, Atype.INT_ATTR_TYPE, goodValMap,
                Arrays.asList(new Integer[]{6, 22}),
                Arrays.asList(new Integer[]{7})); **/
        tryBadRestrictions("int_badminandchoices", ftype, restMap);

        // setup valid maxval and choices -- this should now fail
        restMap.clear();
        restMap.put("choices", goodChoices);
        restMap.put("maxval", new Integer(10));
        tryBadRestrictions("int_badmaxandchoices", ftype, restMap);
        /***
        this.testRestriction(a1, "int_goodmaxandchoices", restMap, ftype, Atype.INT_ATTR_TYPE, goodValMap,
                Arrays.asList(new Integer[]{7, 20}),
                Arrays.asList(new Integer[]{11}));
         * ***/

        // setup valid range
        restMap.clear();
        restMap.put("minval", new Integer(5));
        restMap.put("maxval", new Integer(10));
        this.testRestriction(a1, "int_goodrange", restMap, ftype, Atype.INT_ATTR_TYPE, goodValMap,
                Arrays.asList(new Integer[]{5, 6, 8, 10}),
                Arrays.asList(new Integer[]{11, 20}));

        // add choices to range -- this should now fail
        restMap.put("choices", goodChoices);
        tryBadRestrictions("int_badrangeandchoices", ftype, restMap);
        /***
        this.testRestriction(a1, "int_goodrangeandchoices", restMap, ftype, Atype.INT_ATTR_TYPE, goodValMap,
                Arrays.asList(new Integer[]{6, 8, 20}),
                Arrays.asList(new Integer[]{11})); ***/

        testJsonIO(doc, a1, goodValMap, Atype.INT_ATTR_TYPE);
    }

    @Test
    public void testFloatExtended() throws MATDocumentException, AnnotationException {
        MATDocument doc = new MATDocument();
        doc.setSignal("This is a test document.");
        Atype ftype = doc.findOrAddAtype("AttrTest");
        Annotation a1 = doc.createAnnotation(ftype, 0, 4);
        Map goodValMap = new HashMap();

        // test invalid restrictions
        Map restMap = new HashMap();
        restMap.put("minval", Boolean.TRUE);
        tryBadRestrictions("float_badminval", ftype, restMap);
        restMap.clear();
        restMap.put("maxval", "7.4");
        tryBadRestrictions("float_badmaxval", ftype, restMap);

        // setup valid minval restriction
        restMap.clear();
        restMap.put("minval", new Float(10.5));
        this.testRestriction(a1, "float_goodminval", restMap, ftype, Atype.FLOAT_ATTR_TYPE, goodValMap,
                Arrays.asList(new Float[]{new Float(11.1)}),
                Arrays.asList(new Float[]{new Float(9.5)}));

        // setup valid maxval restriction
        restMap.clear();
        restMap.put("maxval", new Float(20));
        this.testRestriction(a1, "float_goodmaxval", restMap, ftype, Atype.FLOAT_ATTR_TYPE, goodValMap,
                Arrays.asList(new Float[]{new Float(15.6)}),
                Arrays.asList(new Float[]{new Float(22)}));

        // setup valid range restriction
        restMap.clear();
        restMap.put("minval", new Float(5));
        restMap.put("maxval", new Float(10));
        this.testRestriction(a1, "float_goodramge", restMap, ftype, Atype.FLOAT_ATTR_TYPE, goodValMap,
                Arrays.asList(new Float[]{new Float(6.3)}),
                Arrays.asList(new Float[]{new Float(10.01), new Float(4.5)}));

        testJsonIO(doc, a1, goodValMap, Atype.FLOAT_ATTR_TYPE);

        // test that ints in a float are decoded properly
        System.out.println("starting floatIntTest");
        AnnotationCore a = doc.createAnnotation("floatIntTest", 0, 4);
        a.getParentAtype().findOrAddAttribute("floatAttr", Atype.FLOAT_ATTR_TYPE);
        a.getParentAtype().findOrAddAttribute("floatSetAttr", Atype.FLOAT_ATTR_TYPE, AttributeType.SET_AGGREGATION);
        a.setAttributeValue("floatAttr", 6.0);
        a.setAttributeValue("floatSetAttr", new AttributeValueSet(new HashSet(Arrays.asList(new Float[]{new Float(7.0)}))));
        MATJSONEncoding e = new MATJSONEncoding();
        Map jsonNode = e.toJsonNode(doc);
        List asets = (List) jsonNode.get("asets");
        for (Iterator i = asets.iterator(); i.hasNext();) {
            Map aEntry = (Map) i.next();
            if ("floatIntTest".equals(aEntry.get("type"))) {
                List annot = (List) ((List) aEntry.get("annots")).get(0);
                annot.set(2, 6);
                annot.set(3, Arrays.asList(new Integer[]{new Integer(7)}));
                break;
            }
        }
        MATDocument d2 = new MATDocument();
        e.fromEncodedString(d2, e.toEncodedString(jsonNode));
        AnnotationCore a2 = d2.getAnnotationsOfType("floatIntTest").get(0);
        assertTrue(a2.getAttributeValue("floatAttr") instanceof Float);
        assertTrue(a2.getAttributeValue("floatAttr").equals(a.getAttributeValue("floatAttr")));
        // this is a pain to assert
        assertTrue(((AttributeValueCollection) a2.getAttributeValue("floatSetAttr")).collectionEquals((AttributeValueCollection) a.getAttributeValue("floatSetAttr")));
    }

    @Test
    public void testAnnotationExtended() throws AnnotationException, MATDocumentException {
        MATDocument doc = new MATDocument();
        doc.setSignal("This is a test document.");
        Atype ftype = doc.findOrAddAtype("AttrTest");
        Annotation a0 = doc.createAnnotation(ftype, 0, 4);
        Map goodValMap = new HashMap();

        Map aMap = new HashMap();
        aMap.put("a1", "a");
        aMap.put("a2", "a");
        Map bMap = new HashMap();
        bMap.put("a1", "b");
        bMap.put("a2", "b");
        Map a1aMap = new HashMap();
        a1aMap.put("a1", "a");
        Map a2bMap = new HashMap();
        a2bMap.put("a2", "b");

        // I need to make the attributes "choice attributes" so that they're 
        // valid attributes for a complex restriction
        // findOrAddAttribute(String attrName, String attrtype, int aggregation, Map restrictions)
        Map choiceMap = new HashMap();
        choiceMap.put("choices", Arrays.asList(new String[]{"a","b"}));
        Atype ftype1 = doc.findOrAddAtype("Lab1");
        ftype1.findOrAddAttribute("a1", Atype.STRING_ATTR_TYPE, AttributeType.NONE_AGGREGATION, choiceMap);
        ftype1.findOrAddAttribute("a2", Atype.STRING_ATTR_TYPE, AttributeType.NONE_AGGREGATION, choiceMap);
        Atype ftype2 = doc.findOrAddAtype("Lab2");
        ftype2.findOrAddAttribute("a1", Atype.STRING_ATTR_TYPE, AttributeType.NONE_AGGREGATION, choiceMap);
        ftype2.findOrAddAttribute("a2", Atype.STRING_ATTR_TYPE, AttributeType.NONE_AGGREGATION, choiceMap);
        Annotation a1 = doc.createAnnotation(ftype1, 0, 4, aMap);
        Annotation a2 = doc.createAnnotation(ftype2, 0, 4, bMap);
        Annotation a3 = doc.createAnnotation("Lab3", 0, 4);
        Annotation a4 = doc.createAnnotation(ftype1, 0, 4, bMap);
        Annotation a5 = doc.createAnnotation(ftype2, 0, 4, aMap);

        // test invalid restrictions
        Map restMap = new HashMap();
        restMap.put("label_restrictions", "Lab1");
        this.tryBadRestrictions("annot_badrest", ftype1, restMap);

        // setup valid atomic restriction
        restMap.put("label_restrictions", new HashSet(Arrays.asList(new String[]{"Lab1"})));
        this.testRestriction(a0, "labr1", restMap, ftype, Atype.ANNOTATION_ATTR_TYPE, goodValMap,
                Arrays.asList(new Annotation[]{a1}),
                Arrays.asList(new Annotation[]{a2, a3}));

        // setup a set of 2 valid atomic restrictions
        restMap.put("label_restrictions", new HashSet(Arrays.asList(new String[]{"Lab1", "Lab2"})));
        this.testRestriction(a0, "labr2", restMap, ftype, Atype.ANNOTATION_ATTR_TYPE, goodValMap,
                Arrays.asList(new Annotation[]{a1, a2}),
                Arrays.asList(new Annotation[]{a3}));

        // setup a set of 2 complex restrictions
        ComplexRestriction r1 = new ComplexRestriction("Lab1", a1aMap);
        ComplexRestriction r2 = new ComplexRestriction("Lab2", a2bMap);
        restMap.put("label_restrictions", new HashSet(Arrays.asList(new ComplexRestriction[]{r1, r2})));
        this.testRestriction(a0, "labr3", restMap, ftype, Atype.ANNOTATION_ATTR_TYPE, goodValMap,
                Arrays.asList(new Annotation[]{a1, a2}),
                Arrays.asList(new Annotation[]{a4, a5}));

        // setup a set with one atomic restriction and one complex restriction
        restMap.put("label_restrictions", new HashSet(Arrays.asList(new Object[]{"Lab1", r2})));
        this.testRestriction(a0, "labr4", restMap, ftype, Atype.ANNOTATION_ATTR_TYPE, goodValMap,
                Arrays.asList(new Annotation[]{a1, a2, a4}),
                Arrays.asList(new Annotation[]{a5}));

        testJsonIO(doc, a1, goodValMap, Atype.ANNOTATION_ATTR_TYPE);

    }

    // this is used for Int and Float and Annotation
    private void testRestriction(AnnotationCore a1, String attrName, Map restMap,
            Atype ftype, String attrtype, Map goodValMap, List goodVals, List badVals)
            throws MATDocumentException, AnnotationException {
        ftype.findOrAddAttribute(attrName, attrtype, AttributeType.NONE_AGGREGATION, restMap);
        // try the good values
        for (Iterator i = goodVals.iterator(); i.hasNext();) {
            Object value = i.next();
            // set as an object, and cast to its type, and for numbers, as the basic type

            a1.setAttributeValue(attrName, value);
            if (value instanceof Integer) {
                a1.setAttributeValue(attrName, (Integer) value);
                a1.setAttributeValue(attrName, ((Integer) value).intValue());
            } else if (value instanceof Float) {
                a1.setAttributeValue(attrName, (Float) value);
                a1.setAttributeValue(attrName, ((Float) value).floatValue());
                a1.setAttributeValue(attrName, ((Float) value).doubleValue());
            }
            goodValMap.put(attrName, value);
        }
        // try the bad values
        for (Iterator i = badVals.iterator(); i.hasNext();) {
            tryBadVal(a1, attrName, ftype, i.next());
            /********
            Object value = i.next();
            if (value instanceof Integer) {
            tryBadVal(a1, attrName, ftype, (Integer)value);
            } else if (value instanceof Float) {
            tryBadVal(a1, attrName, ftype, (Float)value);
            }
             ****/
        }
    }

    private void tryBadRestrictions(String attrname, Atype ftype, Map restMap) throws MATDocumentException {
        try {
            ftype.findOrAddAttribute(attrname, Atype.STRING_ATTR_TYPE, AttributeType.NONE_AGGREGATION, restMap);
            fail("findOrAddAttribute should have failed");
        } catch (AnnotationException x) {
            // good, that works
        }
    }

    private void tryBadVal(AnnotationCore a1, String attrname, Atype ftype, Object value) throws MATDocumentException {
        try {
            a1.setAttributeValue(attrname, value);
            fail("attr set should have failed " + attrname + ": " + value);
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("must be a"));
        }

    }

    private void testJsonIO(MATDocument doc, Annotation a1, Map goodValHash, String attrtype) throws MATDocumentException {
        System.out.println("doing JSON IO test for " + attrtype);
        String id = a1.getID(true);
        MATJSONEncoding e = new MATJSONEncoding();
        String encodedString = e.toEncodedString(doc);
        System.out.println(encodedString);
        MATDocument d2 = new MATDocument();
        e.fromEncodedString(d2, encodedString);
        if (!Atype.ANNOTATION_ATTR_TYPE.equals(attrtype)) {
            AnnotationCore a2 = d2.getAnnotationByID(id);
            for (Iterator i = goodValHash.keySet().iterator(); i.hasNext();) {
                String k = (String) i.next();
                assertTrue(goodValHash.get(k).equals(a2.getAttributeValue(k)));
            }
        }
    }

    @Test
    public void testDefaults() throws MATDocumentException, AnnotationException {
        MATDocument doc = new MATDocument();
        doc.setSignal("350 is a really nice number"); // 350 can be a string, int or float
        // Annotation a = doc.createAnnotation("TEST", 0, 3);
        Atype atype = doc.findOrAddAtype("TEST");
        /******************** test STRING attribute defaults *********************/
        // Create a STRING attribute whose default is text span
        atype.findOrAddAttribute("attr1", Atype.STRING_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, null, true);
        // Create a STRING attribute whose default is "attr2-default"
        atype.findOrAddAttribute("attr2", Atype.STRING_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, "attr2-default", false);
        // Try to create a STRING attribute with both a default and default is text span
        try {
            atype.findOrAddAttribute("attr-bad1", Atype.STRING_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, "foo", true);
            fail("attr creation with both default types should have failed");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("can't declare both default value and defaultIsTextSpan"));
        }
        // Try to create an aggregated STRING attribute with a default 
        try {
            atype.findOrAddAttribute("attr-bad2", Atype.STRING_ATTR_TYPE, AttributeType.LIST_AGGREGATION, null, "foo", false);
            fail("attr creation for aggregation with default should have failed");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("can't declare default for aggregated"));
        }
        // Create a couple more attributes to create "gaps" between the 
        // default-valued attributes that will need to be filled with nulls when 
        // creating new annotations
        atype.findOrAddAttribute("attr3", Atype.STRING_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, null, false);
        atype.findOrAddAttribute("attr4", Atype.STRING_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, null, false);
        /***************** test INT attribute defaults **************************/
        // Create a INT attribute whose default is text span
        atype.findOrAddAttribute("attr5", Atype.INT_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, null, true);
        // Create a INT attribute whose default is 3
        atype.findOrAddAttribute("attr6", Atype.INT_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, new Integer(3), false);
        // Try to create a INT attribute with both a default and default is text span
        try {
            atype.findOrAddAttribute("attr-bad3", Atype.INT_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, new Integer(3), true);
            fail("attr creation with both default types should have failed");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("can't declare both default value and defaultIsTextSpan"));
        }
        // Try to create an aggregated INT attribute with a default 
        try {
            atype.findOrAddAttribute("attr-bad4", Atype.INT_ATTR_TYPE, AttributeType.LIST_AGGREGATION, null, new Integer(3), false);
            fail("attr creation for aggregation with default should have failed");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("can't declare default for aggregated"));
        }
        /****************** test FLOAT attribute defaults ***********************/
        // Create a FLOAT attribute whose default is text span
        atype.findOrAddAttribute("attr7", Atype.FLOAT_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, null, true);
        // Create a FLOAT attribute whose default is 3.14
        atype.findOrAddAttribute("attr8", Atype.FLOAT_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, new Float(3.14), false);
        // Try to create a FLOAT attribute with both a default and default is text span
        try {
            atype.findOrAddAttribute("attr-bad5", Atype.FLOAT_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, new Float(3.14), true);
            fail("attr creation with both default types should have failed");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("can't declare both default value and defaultIsTextSpan"));
        }
        // Try to create an aggregated FLOAT attribute with a default 
        try {
            atype.findOrAddAttribute("attr-bad6", Atype.FLOAT_ATTR_TYPE, AttributeType.LIST_AGGREGATION, null, new Float(3.14), false);
            fail("attr creation for aggregation with default should have failed");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("can't declare default for aggregated"));
        }

        /****************** test BOOLEAN attribute defaults ***********************/
        // Create a BOOLEAN attribute whose default is true
        atype.findOrAddAttribute("attr9", Atype.BOOLEAN_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, Boolean.TRUE, false);
        // Try to create a BOOLEAN attribute whose default is text span
        try {
            atype.findOrAddAttribute("attr-bad7", Atype.BOOLEAN_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, null, true);
            fail("attr creation for BOOLEAN with text span default should have failed");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("attribute cannot use text span as default"));
        }
        // Try to create a BOOLEAN attribute with both a default and default is text span
        try {
            atype.findOrAddAttribute("attr-bad8", Atype.BOOLEAN_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, Boolean.TRUE, true);
            fail("attr creation with both default types should have failed");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("attribute cannot use text span as default"));
        }
        // Try to create an aggregated BOOLEAN attribute with a default 
        try {
            atype.findOrAddAttribute("attr-bad9", Atype.BOOLEAN_ATTR_TYPE, AttributeType.LIST_AGGREGATION, null, Boolean.TRUE, false);
            fail("attr creation for aggregation with default should have failed");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("can't declare default for aggregated"));
        }

        /****************** test ANNOTATION attribute defaults ***********************/
        Annotation a_def = doc.createAnnotation("VERB", 5, 7);

        // Create a ANNOTATION attribute whose default is a2
        try {
            atype.findOrAddAttribute("attr-bad10", Atype.ANNOTATION_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, a_def, false);
            fail("attr creation for ANNOTATION with default value should have failed");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("Annotation attribute cannot specify default"));
        }
        // Try to create a ANNOTATION attribute whose default is text span
        try {
            atype.findOrAddAttribute("attr-bad11", Atype.ANNOTATION_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, null, true);
            fail("attr creation for ANNOTATION with text span default should have failed");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("Annotation attribute cannot specify default"));
        }
        // Try to create a ANNOTATION attribute with both a default and default is text span
        try {
            atype.findOrAddAttribute("attr-bad12", Atype.ANNOTATION_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, a_def, true);
            fail("attr creation with both default types should have failed");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("Annotation attribute cannot specify default"));
        }
        // Try to create an aggregated ANNOTATION attribute with a default 
        try {
            atype.findOrAddAttribute("attr-bad13", Atype.ANNOTATION_ATTR_TYPE, AttributeType.LIST_AGGREGATION, null, a_def, false);
            fail("attr creation for aggregation with default should have failed");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("Annotation attribute cannot specify default"));
        }

        // test in spanless annotation
        Atype atype2 = doc.findOrAddAtype("TEST2", false);
        try {
            atype2.findOrAddAttribute("attr-bad14", Atype.STRING_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, null, true);
            fail("attr creationf for text span default on spanless annotation should have failed");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("can't use text span as default for spanless"));
        }

        // Create an annotation and check that all the default values are set correctly
        Annotation a = doc.createAnnotation(atype, 0, 3);
        assertTrue(a.getAttributeValue("attr1").equals("350"));
        assertTrue(a.getAttributeValue("attr2").equals("attr2-default"));
        assertTrue(a.getAttributeValue("attr3") == null);
        assertTrue(a.getAttributeValue("attr4") == null);
        assertTrue(((Integer) a.getAttributeValue("attr5")).intValue() == 350);
        assertTrue(((Integer) a.getAttributeValue("attr6")).intValue() == 3);
        assertTrue(((Float) a.getAttributeValue("attr7")).floatValue() == 350.0f);
        assertTrue(((Float) a.getAttributeValue("attr8")).floatValue() == 3.14f);
        assertTrue((Boolean) a.getAttributeValue("attr9"));

        // This should fail because the string is not eligible to be all of a 
        // String, Float and Int, but this atype has attributes that require the 
        // text span default to be all three
        try {
            Annotation a1 = doc.createAnnotation(atype, 4, 6);
            fail("annot create should have failed");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("is not a valid"));
        }

        // Now test validating types when using text span
        MATDocument doc2 = new MATDocument();
        doc2.setSignal("Here is an integer: 45 and a float 32.1");
        Atype atypeA = doc2.findOrAddAtype("TESTA");
        Atype atypeB = doc2.findOrAddAtype("TESTB");
        Atype atypeC = doc2.findOrAddAtype("TESTC");
        atypeA.findOrAddAttribute("string_attr", Atype.STRING_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, null, true);
        atypeB.findOrAddAttribute("int_attr", Atype.INT_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, null, true);
        atypeC.findOrAddAttribute("float_attr", Atype.FLOAT_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, null, true);

        // good creates
        Annotation annotA1 = doc2.createAnnotation(atypeA, 0, 4);   // string "Here"
        Annotation annotB2 = doc2.createAnnotation(atypeB, 20, 22); // int 45
        Annotation annotC3 = doc2.createAnnotation(atypeC, 35, 39); // float 32.1

        // other creates (some ok, some not)
        try {
            Annotation annotB1 = doc2.createAnnotation(atypeB, 0, 4);   // int "Here" is not ok
            fail("create annot with default-to-span int attriubte over non-int text should fail");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("is not a valid"));
        }
        try {
            Annotation annotC1 = doc2.createAnnotation(atypeC, 0, 4);   // float "Here" is not ok
            fail("create annot with default-to-span float attriubte over non-float text should fail");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("is not a valid"));
        }

        Annotation annotA2 = doc2.createAnnotation(atypeA, 20, 22); // string 45 is ok
        Annotation annotC2 = doc2.createAnnotation(atypeC, 20, 22); // float 45 is ok

        Annotation annotA3 = doc2.createAnnotation(atypeA, 35, 39); // String 32.1 is ok

        try {
            Annotation annotB3 = doc2.createAnnotation(atypeB, 35, 39); // int 32.1 is not ok
            fail("create annot with default-to-span int attribute over non-int text should fail");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("is not a valid"));
        }

        // check is if it's a valid int or float but may not meet the other requirements
        // non-matching choices
        Atype atypeD = doc2.findOrAddAtype("TESTD");
        HashMap restMap = new HashMap();
        restMap.clear();
        List goodChoices = Arrays.asList(new Integer[]{5, 6, 20});
        restMap.put("choices", goodChoices);
        atypeD.findOrAddAttribute("fail-choices", Atype.INT_ATTR_TYPE, AttributeType.NONE_AGGREGATION, restMap, null, true);
        // now this should just set the attribute to null since the default text span is no good
        Annotation annotFC = doc2.createAnnotation(atypeD, 20, 22); // int 45 is not among the choices
        assertTrue(annotFC.getAttributeValue("fail-choices") == null);


        // minval too large
        Atype atypeE = doc2.findOrAddAtype("TESTE");
        restMap.clear();
        restMap.put("minval", new Integer(66));
        atypeE.findOrAddAttribute("fail-minval", Atype.INT_ATTR_TYPE, AttributeType.NONE_AGGREGATION, restMap, null, true);
        Annotation annotFM = doc2.createAnnotation(atypeD, 20, 22); // int 45 is not greater than minval (66)
        assertTrue(annotFM.getAttributeValue("fail-minval") == null);

        // this time put a minval and maxval that surround the text span value
        Atype atypeF = doc2.findOrAddAtype("TESTF");
        restMap.clear();
        restMap.put("minval", new Integer(11));
        restMap.put("maxval", new Integer(50));
        atypeF.findOrAddAttribute("ok-minmax", Atype.INT_ATTR_TYPE, AttributeType.NONE_AGGREGATION, restMap, null, true);
        Annotation annotOMM = doc2.createAnnotation(atypeF, 20, 22); // int 45 is ok here

        // now try a float attribute with restrictions that permit 32.1 and 45
        Atype atypeG = doc2.findOrAddAtype("TESTG");
        restMap.clear();
        restMap.put("minval", new Float(12.5));
        restMap.put("maxval", new Float(63.3));
        atypeG.findOrAddAttribute("ok-minmax", Atype.FLOAT_ATTR_TYPE, AttributeType.NONE_AGGREGATION, restMap, null, true);
        Annotation annotOMM1 = doc2.createAnnotation(atypeG, 35, 39);  // float 32.1 is ok here
        Annotation annotOMM2 = doc2.createAnnotation(atypeG, 20, 22);  // float 45 is ok here

        // finally try a float with restrictions that permit 45 but not 32.1
        Atype atypeH = doc2.findOrAddAtype("TESTH");
        restMap.clear();
        restMap.put("minval", new Float(32.5));
        atypeH.findOrAddAttribute("float-minval", Atype.FLOAT_ATTR_TYPE, AttributeType.NONE_AGGREGATION, restMap, null, true);
        Annotation annotFM1 = doc2.createAnnotation(atypeH, 35, 39);  // float 32.1 is not ok here (attr value should be set to null)
        assertTrue(annotFM1.getAttributeValue("float-minval") == null);
        Annotation annotFM2 = doc2.createAnnotation(atypeH, 20, 22);  // float 45 is ok here

    }
    
    @Test
    public void testComplexAnnotationRestrictions() throws MATDocumentException {
        // first a kosher one
        GlobalAnnotationTypeRepository atr = new GlobalAnnotationTypeRepository(false);
        // java is not so much fun for representing multi-line literal strings containing quotes
        // groovy backtick trick stolen from stack overflow
        String desc = ("{`annotationSetRepository`: {"+
                            "`types`: {" +
                              "`Mention`: {" +
                                "`attrs`: [" +
                                    "{`name`: `type`," +
                                     "`type`: `string`," +
                                     "`choices`: [`PER`, `ORG`, `LOC`]" +
                              "}]}," +
                              "`Filler`: {" +
                                "`attrs`: [" +
                                    "{`name`: `nomtype`," +
                                     "`type`: `string`," +
                                     "`choices`: [`PRO`, `NOM`, `NAM`]" +
                              "}]}," +
                              "`Relation`: {" +
                                "`attrs`: [" +
                                    "{`name`: `RelationArg1`," +
                                     "`type`: `annotation`," +
                                     "`label_restrictions`: [[`Mention`, [[`type`, `PER`]]]]" +
                                    "}," +
                                    "{`name`: `RelationArg2`," +
                                     "`type`: `annotation`," +
                                     "`label_restrictions`: [[`Filler`, [[`nomtype`, `PRO`]]]]" +
                          "}]}}}}").replace('`', '"');   

        atr.fromJSONDescriptor(desc);
        
        
        // this one should work too -- same details in a less convenient order
        atr = new GlobalAnnotationTypeRepository(false);
        desc = ("{`annotationSetRepository`: {"+
                            "`types`: {" +
                              "`Mention`: {" +
                                "`attrs`: [" +
                                    "{`name`: `type`," +
                                     "`type`: `string`," +
                                     "`choices`: [`PER`, `ORG`, `LOC`]" +
                              "}]}," +
                              "`Relation`: {" +
                                "`attrs`: [" +
                                    "{`name`: `RelationArg1`," +
                                     "`type`: `annotation`," +
                                     "`label_restrictions`: [[`Mention`, [[`type`, `PER`]]]]" +
                                    "}," +
                                    "{`name`: `RelationArg2`," +
                                     "`type`: `annotation`," +
                                     "`label_restrictions`: [[`Filler`, [[`nomtype`, `PRO`]]]]" +                
                              "}]}," +
                              "`Filler`: {" +
                                "`attrs`: [" +
                                    "{`name`: `nomtype`," +
                                     "`type`: `string`," +
                                     "`choices`: [`PRO`, `NOM`, `NAM`]" +
                          "}]}}}}").replace('`', '"');   
        atr.fromJSONDescriptor(desc);
        
        // this one should fail because the label restriction isn't an attribute with choices
        try {
            desc = ("{`annotationSetRepository`: {" +
                       "`types`: {" +
                         "`Filler`: {" +
                           "`attrs`: [" +
                             "{" +
                               "`choices`: [" +
                                 "`PRO`," +
                                 "`NOM`," +
                                 "`NAM`]," +
                               "`name`: `nomtype`" +
                             "}," +
                             "{" +
                               "`name`: `comment`" +
                             "}]}," +
                         "`Mention`: {" +
                           "`attrs`: [" +
                             "{" +
                               "`choices`: [" +
                                 "`PER`," +
                                 "`ORG`," +
                                 "`LOC`]," +
                               "`name`: `type`" +
                             "}]}," +
                         "`Relation`: {" +
                          "`attrs`: [" +
                             "{" +
                               "`label_restrictions`: [[" +
                                   "`Mention`," +
                                   "[[" +
                                       "`type`," +
                                       "`PER`" +
                                     "]]]]," +
                               "`name`: `RelationArg1`," +
                               "`type`: `annotation`" +
                             "}," +
                             "{" +
                               "`label_restrictions`: [[" +
                                   "`Filler`," +
                                   "[[" +
                                       "`comment`," +
                                       "`PRO`" +
                                     "]]]]," +
                               "`name`: `RelationArg2`," +
                               "`type`: `annotation`" +
                             "}]}}}}").replace('`', '"');   
            atr.fromJSONDescriptor(desc);
            fail("label restriction on wrong type of attribute should fail");
        } catch (MATDocumentException x) {
            assertTrue(x.getMessage().contains("invalid annotation restriction"));
        }

        // this one should fail because the label restriction isn't on a string or int attribute
        try {
            desc = ("{`annotationSetRepository`: {" +
               "`allAnnotationsKnown`: false," +
               "`types`: {" +
                 "`Filler`: {" +
                   "`attrs`: [" +
                     "{" +
                       "`choices`: [" +
                         "`PRO`," +
                         "`NOM`," +
                         "`NAM`]," +
                       "`name`: `nomtype`" +
                     "}," +
                     "{" +
                       "`name`: `comment`," +
                       "`type`: `float`" +
                     "}]}," +
                 "`Mention`: {" +
                   "`attrs`: [" +
                     "{" +
                       "`choices`: [" +
                         "`PER`," +
                         "`ORG`," +
                         "`LOC`]," +
                       "`name`: `type`" +
                     "}]}," +
                 "`Relation`: {" +
                   "`attrs`: [" +
                     "{" +
                       "`label_restrictions`: [[" +
                           "`Mention`," +
                           "[[" +
                               "`type`," +
                               "`PER`" +
                             "]]]]," +
                       "`name`: `RelationArg1`," +
                       "`type`: `annotation`" +
                     "}," +
                     "{" +
                       "`label_restrictions`: [[" +
                           "`Filler`," +
                           "[[" +
                               "`comment`," +
                              " 5.6" +
                             "]]]]," +
                       "`name`: `RelationArg2`," +
                       "`type`: `annotation`" +
                     "}]}}}}").replace('`', '"');   
            atr.fromJSONDescriptor(desc);
            fail("label restriction on wrong type of attribute should fail");
        } catch (MATDocumentException x) {
            assertTrue(x.getMessage().contains("restriction value must"));
        }
    }
  
    @Test
    public void testBadValueSets() throws MATDocumentException, AnnotationException {
        // first a kosher one
        GlobalAnnotationTypeRepository atr = new GlobalAnnotationTypeRepository(false);
        String desc = ("{`annotationSetRepository`: {"+
           "`allAnnotationsKnown`: false," +
           "`types`: {" +
             "`Event`: {" +
               "`attrs`: [" +
                 "{" +
                   "`label_restrictions`: [[" +
                     "`Filler`," +
                       "[[" +
                          "`otherchoice`," +
                          "20" +
                        "]," +
                        "[" +
                           "`nomtype`," +
                           "`PRO`" +
                         "]]]," +
                     "`OtherFiller`," +
                     "[" +
                       "`Filler`," +
                       "[[" +
                           "`nomtype`," +
                           "`NAM`" +
                        "]]]]," +
                   "`name`: `EventArg`," +
                   "`type`: `annotation`" +
                 "}]}," +
             "`Filler`: {" +
               "`attrs`: [" +
                 "{" +
                   "`choices`: [" +
                     "`PRO`," +
                     "`NOM`," +
                     "`NAM`]," +
                   "`name`: `nomtype`" +
                "}," +
                "{" +
                   "`choices`: [" +
                    "10," +
                    "20," +
                    "30]," +
                   "`name`: `otherchoice`," +
                   "`type`: `int`" +
                 "}]}," +
             "`OtherFiller`: {}," +
             "`Relation`: {" +
               "`attrs`: [" +
                 "{" +
                   "`label_restrictions`: [[" +
                       "`Filler`," +
                       "[[" +
                           "`nomtype`," +
                           "`PRO`" +
                        "]]]," +
                     "[" +
                       "`Filler`," +
                       "[[" +
                           "`otherchoice`," +
                          " 10" +
                         "]," +
                         "[" +
                           "`nomtype`," +
                           "`NAM`" +
                         "]]]," +
                     "[" +
                       "`Filler`," +
                       "[[" +
                           "`otherchoice`," +
                          " 30" +
                         "]]]]," +
                   "`name`: `RelationArg`," +
                   "`type`: `annotation`" +
                 "}]}}}}").replace('`', '"');   
        atr.fromJSONDescriptor(desc);

        MATDocument doc = new MATDocument(atr);
        doc.setSignal("This is a test document.");
        Annotation r = doc.createAnnotation("Relation", 0, 5);
        Annotation e = doc.createAnnotation("Event", 5, 10);
        Annotation f = doc.createAnnotation("Filler", 10, 15);
        // it's got no attributes, so it shouldn't fill
        try  {
            r.setAttributeValue("RelationArg", f);
            fail("relation attribute arg set should have failed");
        } catch (AnnotationException x) {
            System.err.println(x.getMessage());
            assertTrue(x.getMessage().contains("satisfy other restrictions"));
        }

        // now these features should allow it to satisfy both arguments
        f.setAttributeValue("nomtype", "PRO");
        f.setAttributeValue("otherchoice", 20);
        r.setAttributeValue("RelationArg", f);
        e.setAttributeValue("EventArg", f);
        
        //  now try to change the nomtype attr to something that doesn't satisfy the restrictions
        try {
            f.setAttributeValue("nomtype", "NAM");
            fail("should not be able to change nomtype to invalid value for subordinate");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("inconsistent with the attribute restrictions"));
        }
        
        // now detach from the relation and change it (still attached to the event, which 
        // requires NAM or PRO/30)
        r.setAttributeValue("RelationArg", (AnnotationCore)null);
        f.setAttributeValue("nomtype", "NAM");
        f.setAttributeValue("otherchoice", 30);
        // then reattach to the relation which requires PRO or NAM/10 or 30
        r.setAttributeValue("RelationArg", f);
        
        // changing otherchoice to 10 will work (NAM/10 is ok)
        f.setAttributeValue("otherchoice", 10);
        
        // but 20 should not
         try {
            f.setAttributeValue("otherchoice", 20);
            fail("should not be able to change otherchoice to invalid value for subordinate");
        } catch (AnnotationException x) {
            assertTrue(x.getMessage().contains("inconsistent with the attribute restrictions"));
        }
    }
    @Test
    public void testSpannedAnnotationGetters() throws MATDocumentException, AnnotationException {
        MATDocument doc = new MATDocument();
        doc.setSignal(this.DOC_TEXT);
        Annotation a = doc.createAnnotation("TYPEA", 0, 5);
        Annotation b = doc.createAnnotation("TYPEA", 10, 15);
        Annotation c = doc.createAnnotation("TYPEB", 4, 8);
        Annotation d = doc.createAnnotation("TYPEB", 4, 6);
        Annotation e = doc.createAnnotation("TYPEC", 4, 7);
        // Correct sorting of these annotations is a, d, e, c, b
        List spannedList = doc.getSpannedAnnotations();
        assertTrue(spannedList.size() == 5);
        List<Annotation> orderedList = doc.getOrderedAnnotations();
        assertTrue(orderedList.size() == 5);
        assertTrue(orderedList.get(0).getStartIndex() == 0);
        assertTrue(orderedList.get(1).getStartIndex() == 4);
        assertTrue(orderedList.get(2).getStartIndex() == 4);
        assertTrue(orderedList.get(3).getStartIndex() == 4);
        assertTrue(orderedList.get(4).getStartIndex() == 10);
        assertTrue(orderedList.get(1).getEndIndex() == 6);
        assertTrue(orderedList.get(2).getEndIndex() == 7);
        assertTrue(orderedList.get(3).getEndIndex() == 8);
    }
    
    @Test
    public void testSpanlessAnnotationGetter() throws MATDocumentException, AnnotationException {
        MATDocument doc = createSpanlessDoc(); // has 3 spanned annots and one spanless
        // add another spanless
        SpanlessAnnotation a = doc.createSpanlessAnnotation("OTHER");
        a.setAttributeValue("silly", "yes");
        List<SpanlessAnnotation> spanlessList = doc.getSpanlessAnnotations();
        assertTrue(spanlessList.size() == 2);
        assertTrue(spanlessList.contains(a));
        assertTrue(doc.getAllAnnotations().size() == 5);     
    }    

   
    @Test
    public void testComplexAnnotationValuedAttribute() throws MATDocumentException, AnnotationException, IOException { 
        GlobalAnnotationTypeRepository atr = new GlobalAnnotationTypeRepository(false);
        String desc = ("{`annotationSetRepository`: {"+
                            "`types`: {" +
                              "`FILLER`: {}," +
                              "`ENAMEX`: {" +
                                "`attrs`: [" +
                                    "{`name`: `type`," +
                                     "`type`: `string`," +
                                     "`choices`: [`PER`, `LOC`, `ORG`]}," +
                                     "{`name`: `annot_attr`," +
                                      "`type`:`annotation`," +
                                      "`label_restrictions`: [[`FILLER`, []]]" +
                              "}]}," +
                              "`EVENT`: {" +
                                "`attrs`: [" +
                                    "{`name`: `enamex`," +
                                     "`type`: `annotation`," +
                                     "`label_restrictions`: [[`ENAMEX`, [[`type`, `PER`]]]]" +
                              "}]}}}}").replace('`', '"');   
        atr.fromJSONDescriptor(desc);
        MATDocument doc = new MATDocument(atr);
        doc.setSignal(this.DOC_TEXT);
        Annotation filler = doc.createAnnotation("FILLER", 0, 3);
        Annotation enamex = doc.createAnnotation("ENAMEX", 7, 10);
        enamex.setAttributeValue("type", "PER");
        enamex.setAttributeValue("annot_attr", filler);
        Annotation event = doc.createAnnotation("EVENT", 15, 20);
        event.setAttributeValue("enamex", enamex);
        // serialize and deserialize
        MATJSONEncoding e = new MATJSONEncoding();
        String s = e.toEncodedString(doc);
        System.out.println(s);
        // in order to propoerly test the deserialization, I need it to deserialize 
        // the EVENT before the ENAMEX and it is a huge pain to guarantee that
        MATDocument newDoc = new MATDocument(atr);
        JsonFactory jsonFact = new JsonFactory();
        JsonParser parser = jsonFact.createJsonParser(new StringReader(s));
        JsonNode jsonValues = new ObjectMapper().readTree(parser);
        // grab the list of asets out of the jsonValues node and re-organize it 
        // so EVENT is first by finding and removing the EVENT node from the
        // list, and then re-inserting it at the front
        ArrayNode asetsValues = (ArrayNode) jsonValues.path("asets");
        JsonNode eventNode = null;
        for (int i=0; i<asetsValues.size(); i++) {
            JsonNode n = asetsValues.get(i);
            String theType = n.path("type").getTextValue();
            if (theType.equals("EVENT")) {
                eventNode = n;
                asetsValues.remove(i);
                break;
            }
        }
        asetsValues.insert(0,eventNode);
        e.fromJsonNode(newDoc, jsonValues);
        
    }
}


