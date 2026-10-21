'use strict';

// Static-room branch of Rain World's Futile/Projection shader. Room camera PNGs
// encode depth in red; projections.py preserves that before palette decoding.
// _GrabTexture (moving creatures and objects) is only available inside the game.
const MIProjectionDepth = (() => {
  function bounds(pose, size, scene) {
    const angle = pose.rotation * Math.PI / 180, cosine = Math.cos(angle), sine = Math.sin(angle);
    const halfWidth = Math.abs(pose.scale) * (Math.abs(cosine) * size[0] + Math.abs(sine) * size[1]) / 2;
    const halfHeight = Math.abs(pose.scale) * (Math.abs(sine) * size[0] + Math.abs(cosine) * size[1]) / 2;
    const x = Math.max(0, Math.floor(pose.x * scene[0] - halfWidth));
    const y = Math.max(0, Math.floor(pose.y * scene[1] - halfHeight));
    const right = Math.min(scene[0], Math.ceil(pose.x * scene[0] + halfWidth));
    const bottom = Math.min(scene[1], Math.ceil(pose.y * scene[1] + halfHeight));
    return [x, y, Math.max(0, right - x), Math.max(0, bottom - y)];
  }

  // Reference sampler used in regression checks, in top-origin pixel space.
  // Keep the 1..1000 image-size encoding: the game shader reads vertex RGB.
  function sourcePixel(point, pose, size, scene, depth, light) {
    const angle = pose.rotation * Math.PI / 180, cosine = Math.cos(angle), sine = Math.sin(angle);
    const dx = point[0] - pose.x * scene[0], dy = point[1] - pose.y * scene[1];
    const x = (cosine * dx + sine * dy) / pose.scale + size[0] / 2;
    const y = (-sine * dx + cosine * dy) / pose.scale + size[1] / 2;
    if (x < 0 || y < 0 || x >= size[0] || y >= size[1]) return null;
    return [x - light[0] * (depth - 5) * size[0] / Math.min(1000, Math.max(1, size[0])),
            y - light[1] * (depth - 5) * size[1] / Math.min(1000, Math.max(1, size[1]))];
  }

  function createRenderer() {
    let canvas, gl, program, uniforms, maxSize, depthImage = null, depthTexture = null;
    const textures = new Map();
    try {
      canvas = document.createElement('canvas');
      gl = canvas.getContext('webgl', {alpha:true, antialias:false, premultipliedAlpha:false, preserveDrawingBuffer:true});
      if (!gl || !gl.getShaderPrecisionFormat(gl.FRAGMENT_SHADER, gl.HIGH_FLOAT).precision) return null;
      function compile(type, source) {
        const shader = gl.createShader(type); gl.shaderSource(shader, source); gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {gl.deleteShader(shader); throw Error('Projection depth shader compilation failed');}
        return shader;
      }
      const vertex = compile(gl.VERTEX_SHADER, 'attribute vec2 position; void main(){gl_Position=vec4(position,0.,1.);}');
      const fragment = compile(gl.FRAGMENT_SHADER, `
        precision highp float;
        uniform sampler2D image, depthMap;
        uniform vec2 sceneSize, imageSize, light, origin, outputSize, center, rotation;
        uniform float scale;
        void main(){
          vec2 point=origin+vec2(gl_FragCoord.x,outputSize.y-gl_FragCoord.y);
          vec2 delta=(point-center)/scale;
          vec2 local=vec2(rotation.x*delta.x+rotation.y*delta.y,-rotation.y*delta.x+rotation.x*delta.y);
          vec2 uv=local/imageSize+vec2(.5);
          if(any(lessThan(uv,vec2(0.)))||any(greaterThanEqual(uv,vec2(1.)))) discard;
          vec4 encoded=texture2D(depthMap,point/sceneSize);
          if(encoded.g<.5||encoded.a<.5) discard;
          float depth=floor(encoded.r*255.+.5);
          uv-=light*(depth-5.)/clamp(imageSize,vec2(1.),vec2(1000.));
          gl_FragColor=texture2D(image,uv);
        }`);
      program = gl.createProgram(); gl.attachShader(program, vertex); gl.attachShader(program, fragment); gl.linkProgram(program);
      gl.deleteShader(vertex); gl.deleteShader(fragment);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw Error('Projection depth shader link failed');
      gl.useProgram(program);
      const buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW);
      const position = gl.getAttribLocation(program, 'position'); gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
      uniforms = Object.fromEntries(['image','depthMap','sceneSize','imageSize','light','origin','outputSize','center','rotation','scale'].map(key => [key,gl.getUniformLocation(program,key)]));
      gl.uniform1i(uniforms.image, 0); gl.uniform1i(uniforms.depthMap, 1);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
      gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
      gl.disable(gl.BLEND); gl.clearColor(0,0,0,0);
      maxSize = Math.min(gl.getParameter(gl.MAX_TEXTURE_SIZE), gl.getParameter(gl.MAX_RENDERBUFFER_SIZE));
    } catch {return null;}

    function upload(image) {
      const texture = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,texture);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
      gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);
      return texture;
    }

    return {
      // Returns false if a safe flat-preview fallback is required. Each image is
      // rendered only within its transformed bounds, not into a full-room FBO.
      draw(context, image, depth, pose, size, scene, light) {
        if (gl.isContextLost() || !depth || !image || pose.scale <= 0) return false;
        const box = bounds(pose,size,scene);
        if (!box[2] || !box[3]) return true;
        if ([...scene,...size,box[2],box[3]].some(value => value > maxSize) || box[2]*box[3] > 8*1024*1024) return false;
        try {
          if (canvas.width !== box[2]) canvas.width = box[2];
          if (canvas.height !== box[3]) canvas.height = box[3];
          gl.viewport(0,0,box[2],box[3]); gl.clear(gl.COLOR_BUFFER_BIT);
          gl.activeTexture(gl.TEXTURE1);
          if (depthImage !== depth) {if (depthTexture) gl.deleteTexture(depthTexture); depthTexture=upload(depth);depthImage=depth;}
          gl.bindTexture(gl.TEXTURE_2D,depthTexture);
          gl.activeTexture(gl.TEXTURE0);
          if (!textures.has(image)) {
            if (textures.size >= 24) {const old=textures.keys().next().value;gl.deleteTexture(textures.get(old));textures.delete(old);}
            textures.set(image,upload(image));
          }
          gl.bindTexture(gl.TEXTURE_2D,textures.get(image));
          gl.uniform2f(uniforms.sceneSize,...scene); gl.uniform2f(uniforms.imageSize,...size); gl.uniform2f(uniforms.light,...light);
          gl.uniform2f(uniforms.origin,box[0],box[1]); gl.uniform2f(uniforms.outputSize,box[2],box[3]);
          gl.uniform2f(uniforms.center,pose.x*scene[0],pose.y*scene[1]); gl.uniform1f(uniforms.scale,pose.scale);
          const angle=pose.rotation*Math.PI/180; gl.uniform2f(uniforms.rotation,Math.cos(angle),Math.sin(angle));
          gl.drawArrays(gl.TRIANGLES,0,6);
          if (gl.getError() !== gl.NO_ERROR) return false;
          context.drawImage(canvas,box[0],box[1]);
          return true;
        } catch {return false;}
      }
    };
  }
  return {bounds, sourcePixel, createRenderer};
})();
if (typeof module !== 'undefined' && module.exports) module.exports = MIProjectionDepth;
