// Wrappers for Matter Bodies that instantiate a particular BlockKind

exports.Block = function(blockKind, x, y, rotated, testing_placement = false, x_index = null,  y_index = null) {

    this.blockKind = blockKind;
    this.x_index = x_index;
    this.y_index = y_index;
    this.color = this.blockKind.blockColor;

    if (rotated) {
        this.w = blockKind.h * sF;
        this.h = blockKind.w * sF;
    } else {
        this.w = blockKind.w * sF;
        this.h = blockKind.h * sF;
    }

    //var options = blockKind.options;

    var options = {
        friction: 0.9,
        frictionStatic: 1.4,
        //frictionAir: 0.07,
        density: 0.0035,
        restitution: 0.0015,
        sleepThreshold: 30
    }
    if (!testing_placement) {
        this.originalX = x * worldScale;
        this.originalY = y * worldScale;

        this.body = Bodies.rectangle(this.originalX, this.originalY, this.w * worldScale, this.h * worldScale, options);
        World.add(engine.world, this.body); //this where a block gets added to matter
    }
    else {
        this.test_body = Bodies.rectangle(x * worldScale, y * worldScale, this.w * worldScale * 0.85, this.h * worldScale * 0.85);
        this.test_body.collisionFilter.category = 3;
    }


    // Display the block
    this.show = function (env) {

        var pos = this.body.position;
        var angle = this.body.angle;

        env.push(); //saves the current drawing style settings and transformations
        env.rectMode(env.CENTER);
        env.translate(pos.x / worldScale, pos.y / worldScale);
        env.rotate(angle);
        env.stroke([28,54,62]);
        env.strokeWeight(2);
        env.fill(this.color);
        // if(this.body.isSleeping) {
        //     env.fill();
        // }

        if (!chocolateBlocks) {
            env.rect(0, 0, this.w, this.h);
        }
        else {
            this.blockKind.drawChocolateBlocks(env);
        }
        env.pop();

    }

    this.can_be_placed = function () {
        //check if the current block is in the scope by looking at the global variable set by showGhost
        if (!current_block_placement_allowed){return false;}
        bounds = this.test_body.bounds;
        // update bound to ensure that a block can only be placed when no other block covering it
        bounds['min']['y'] = 0.; //imagine a very tall block
        colliding_bodies = Matter.Query.region(engine.world.bodies, bounds); //testing against the body boundaries from matter.js
         return (colliding_bodies === undefined || colliding_bodies.length == 0)
    }

    this.checkMotion = function () {
        //console.log('angle', this.body.angle);
        //console.log('∆x', this.body.position.x - this.originalX);
        //console.log('∆y', this.body.position.y - this.originalY);

        var xMove = Math.abs(this.body.position.x - this.originalX) > 10;
        var yMove = Math.abs(this.body.position.y - this.originalY) > 10;
        var rotated = Math.abs(this.body.angle) > 0.70

        return (xMove || yMove || rotated)
    }

}



exports.Boundary = function Boundary(x, y, w, h){
    var options = {
        isStatic: true, // static i.e. not affected by gravity
        friction: 0.9,
        frictionStatic: 2
        //slop: 0,
        //restitution: 0
    }
    this.w = w;
    this.h = h;
    this.body = Bodies.rectangle(x*worldScale,y*worldScale,w*worldScale,h*worldScale, options);
    World.add(engine.world, this.body); 
}

exports.options = {
    friction: 0.9,
    frictionStatic: 1.4,
    //frictionAir: 0.07,
    density: 0.0035,
    restitution: 0.0015,
    sleepThreshold: 30
}