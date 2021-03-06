import openvoronoi as ovd    # https://github.com/aewallin/openvoronoi
import ttt                   # https://github.com/aewallin/truetype-tracer
import ngc_writer            # https://github.com/aewallin/linuxcnc-scripts
import time


ngc_writer.clearance_height = 10
ngc_writer.feed_height = 2
ngc_writer.feed = 200

scale = 300

# ofs is a list of moves.
def printOffsets(ofs):
    nloop = 0
    for lop in ofs:
        n = 0
        N = len(lop)
        first_point=[]
        previous=[]
        for p in lop:
            # p[0] is the Point
            # p[1] is -1 for lines, and r for arcs
            if n==0: # don't draw anything on the first iteration
                previous=p[0]
                ngc_writer.pen_up()
                ngc_writer.xy_rapid_to( scale*previous.x, scale*previous.y)
                ngc_writer.pen_down()
            else:
                cw=p[3]  # cw or ccw arc
                cen=p[2] # center of arc
                r=p[1]   # radius of arc
                p=p[0]   # target position
                if r==-1: # -1 means line
                    ngc_writer.xy_line_to( scale*p.x, scale*p.y )
                else:
                    ngc_writer.xy_arc_to( scale*p.x, scale*p.y, scale*r, scale*cen.x, scale*cen.y, cw ) 
                previous=p
            n=n+1
        nloop = nloop+1
        
# this function inserts point-sites into vd
def insert_polygon_points(vd, polygon):
    pts=[]
    for p in polygon:
        pts.append( ovd.Point( p[0], p[1] ) )
    id_list = []
    #print "inserting ",len(pts)," point-sites:"
    m=0
    for p in pts:
        id_list.append( vd.addVertexSite( p ) )
        #print " ",m," added vertex ", id_list[ len(id_list) -1 ]
        m=m+1    
    return id_list

# this function inserts line-segments into vd
def insert_polygon_segments(vd,id_list):
    j=0
    #print "inserting ",len(id_list)," line-segments:"
    for n in range(len(id_list)):
        n_nxt = n+1
        if n==(len(id_list)-1):
            n_nxt=0
        #print " ",j,"inserting segement ",id_list[n]," - ",id_list[n_nxt]
        vd.addLineSite( id_list[n], id_list[n_nxt])
        j=j+1

# this function takes all segments from ttt and inserts them into vd
def insert_many_polygons(vd,segs):
    polygon_ids =[]
    t_before = time.time()
    for poly in segs:
        poly_id = insert_polygon_points(vd,poly)
        polygon_ids.append(poly_id)
    t_after = time.time()
    pt_time = t_after-t_before
    
    t_before = time.time()
    for ids in polygon_ids:
        insert_polygon_segments(vd,ids)
    
    t_after = time.time()
    seg_time = t_after-t_before
    
    return [pt_time, seg_time]

# this translates segments from ttt
def translate(segs,x,y):
    out = []
    for seg in segs:
        seg2 = []
        for p in seg:
            p2 = []
            p2.append(p[0] + x)
            p2.append(p[1] + y)
            seg2.append(p2)
        out.append(seg2)
    return out
    
# modify by deleting last point (since it is identical to the first point)
def modify_segments(segs):
    segs_mod =[]
    for seg in segs:
        first = seg[0]
        last = seg[ len(seg)-1 ]
        assert( first[0]==last[0] and first[1]==last[1] )
        seg.pop()
        seg.reverse() # to get interior or exterior offsets. Try commenting out this and see what happens.
        segs_mod.append(seg)
    return segs_mod
    
# get segments from ttt
def ttt_segments(text,scale):
    wr = ttt.SEG_Writer()
    wr.arc = False   # approximate arcs with lines
    wr.conic = False # approximate conic with arc/line
    wr.cubic = False # approximate cubic with arc/line
    
    # these parameters influence how we subdivide curves
    wr.conic_biarc_subdivision = 50
    wr.conic_line_subdivision = 50
    wr.cubic_biarc_subdivision = 50
    wr.cubic_line_subdivision = 50
    
    wr.scale = float(1)/float(scale)
    ttt.ttt(text,wr) 
    segs = wr.get_segments()
    return segs

    
if __name__ == "__main__":  
    vd = ovd.VoronoiDiagram(1,120) # parameters: (r,bins)  
    # float r  = radius within which all geometry is located. it is best to use 1 (unit-circle) for now.
    # int bins = number of bins for grid-search (affects performance, should not affect correctness)
    
    print "( TTT++",ttt.version()," )"
    print "( OpenVoronoi",ovd.version()," )"
    
    # get segments from ttt. NOTE: must set scale so all geometry fits within unit-circle!
    segs = ttt_segments(  "LinuxCNC", 20000) # (text, scale) all coordinates are divided by scale
    segs = translate(segs, -0.06, 0.05)
    segs = modify_segments(segs)
    
    times = insert_many_polygons(vd,segs) # insert segments into vd
    print "( all sites inserted in %.3f seconds )" % ( sum(times))
    print "( VD check: ", vd.check(), " )"
    
    pi = ovd.PolygonInterior( True ) # polygon interior
    vd.filter_graph(pi)
    
    of = ovd.Offset( vd.getGraph() ) # pass the filtered graph to the Offset class

    ofs_list=[]
    t_before = time.time()
    for t in [0.003*x for x in range(1,20)]: # this defines the "step-over" and how many offsets we get
        ofs = of.offset(t) # generate offset with offset-distance t
        ofs_list.append(ofs)
    t_after = time.time()
    oftime = t_after-t_before
    print "( offsets generated in %.3f seconds )" % ( oftime )
    
    ngc_writer.preamble()
    
    for ofs in ofs_list:
        printOffsets(ofs)
    
    ngc_writer.postamble()
